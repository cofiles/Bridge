// Own the system proxy only while the parent holds our stdin pipe open.
#import <Foundation/Foundation.h>
#import <SystemConfiguration/SystemConfiguration.h>
#import <Security/Authorization.h>
#include <unistd.h>
#include <signal.h>

static NSString *primaryService(void) {
    for (NSString *family in @[@"IPv4", @"IPv6"]) {
        NSString *key = [@"State:/Network/Global/" stringByAppendingString:family];
        NSDictionary *state = CFBridgingRelease(SCDynamicStoreCopyValue(NULL, (__bridge CFStringRef)key));
        if (state[@"PrimaryService"]) return state[@"PrimaryService"];
    }
    return nil;
}

static NSDictionary *proxyValues(NSNumber *port) {
    return @{@"HTTPEnable": @1, @"HTTPSEnable": @1,
             @"HTTPProxy": @"127.0.0.1", @"HTTPSProxy": @"127.0.0.1",
             @"HTTPPort": port, @"HTTPSPort": port,
             @"ProxyAutoConfigEnable": @0, @"ProxyAutoDiscoveryEnable": @0};
}

// Merge inside a preferences lock so unrelated network changes survive disconnect.
static BOOL change(SCPreferencesRef prefs, NSString *serviceID, NSDictionary *values,
                   NSDictionary **previous, BOOL restore, BOOL *committed) {
    SCPreferencesSynchronize(prefs);
    if (!SCPreferencesLock(prefs, TRUE)) return NO;
    SCNetworkServiceRef service = SCNetworkServiceCopy(prefs, (__bridge CFStringRef)serviceID);
    SCNetworkProtocolRef proto = service ? SCNetworkServiceCopyProtocol(service, kSCNetworkProtocolTypeProxies) : NULL;
    BOOL ok = NO;
    if (proto && SCNetworkProtocolGetEnabled(proto)) {
        NSDictionary *current = (__bridge NSDictionary *)SCNetworkProtocolGetConfiguration(proto) ?: @{};
        NSMutableDictionary *next = [current mutableCopy];
        if (!restore) {
            *previous = [current copy];
            [next addEntriesFromDictionary:values];
        } else {
            // If a user replaced either proxy endpoint, preserve their whole endpoint.
            for (NSArray *group in @[@[@"HTTPEnable", @"HTTPProxy", @"HTTPPort"],
                                     @[@"HTTPSEnable", @"HTTPSProxy", @"HTTPSPort"],
                                     @[@"ProxyAutoConfigEnable"], @[@"ProxyAutoDiscoveryEnable"]]) {
                BOOL ours = YES;
                for (NSString *k in group) if (![current[k] isEqual:values[k]]) ours = NO;
                if (ours) for (NSString *k in group) next[k] = (*previous)[k];
            }
        }
        if ([current isEqual:next]) ok = YES;
        else if (SCNetworkProtocolSetConfiguration(proto, (__bridge CFDictionaryRef)next)
                 && SCPreferencesCommitChanges(prefs)) {
            *committed = YES;
            ok = SCPreferencesApplyChanges(prefs);
        }
    }
    if (proto) CFRelease(proto);
    if (service) CFRelease(service);
    SCPreferencesUnlock(prefs);
    return ok;
}

static BOOL active(NSDictionary *values) {
    NSDictionary *live = CFBridgingRelease(SCDynamicStoreCopyProxies(NULL));
    for (NSString *key in values) {
        if (![live[key] isEqual:values[key]] && !(live[key] == nil && [values[key] isEqual:@0])) return NO;
    }
    return YES;
}

int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc != 2) return 1;
        int port = atoi(argv[1]);
        if (port < 1 || port > 65535) return 1;
        signal(SIGPIPE, SIG_IGN);
        NSString *service = primaryService();
        if (!service) return 2;
        AuthorizationRef auth = NULL;
        if (AuthorizationCreate(NULL, kAuthorizationEmptyEnvironment, kAuthorizationFlagDefaults, &auth) != errAuthorizationSuccess) return 3;
        SCPreferencesRef prefs = SCPreferencesCreateWithAuthorization(NULL, CFSTR("Bridge"), NULL, auth);
        NSDictionary *values = proxyValues(@(port));
        NSDictionary *saved = nil;
        BOOL committed = NO;
        BOOL ok = prefs && change(prefs, service, values, &saved, NO, &committed);
        if (ok) {
            for (int i = 0; i < 40 && !active(values); i++) usleep(100000);
            ok = active(values);
        }
        if (ok) {
            puts("READY");
            fflush(stdout);
            char byte;
            while (read(STDIN_FILENO, &byte, 1) > 0) {}
        }
        BOOL restored = !committed || change(prefs, service, values, &saved, YES, &committed);
        if (prefs) CFRelease(prefs);
        AuthorizationFree(auth, kAuthorizationFlagDefaults);
        return !restored ? 4 : ok ? 0 : 3;
    }
}
