package app.bridge;
import android.app.*;
import android.content.*;
import android.net.VpnService;
import android.os.*;
public class TunnelService extends VpnService {
 android.net.ConnectivityManager.NetworkCallback networks;
 public void alert(String message) {
  NotificationManager manager=getSystemService(NotificationManager.class);
  manager.createNotificationChannel(new NotificationChannel("alerts","Subscription alerts",NotificationManager.IMPORTANCE_DEFAULT));
  manager.notify(2,new Notification.Builder(this,"alerts").setSmallIcon(R.drawable.icon)
    .setContentTitle("Bridge").setContentText(message).setAutoCancel(true).build());
 }
 void environment() {
  android.net.ConnectivityManager cm=getSystemService(android.net.ConnectivityManager.class);
  StringBuilder key=new StringBuilder();
  for(android.net.Network network:cm.getAllNetworks()){
   android.net.NetworkCapabilities cap=cm.getNetworkCapabilities(network);
   if(cap!=null&&cap.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET)
      &&!cap.hasTransport(android.net.NetworkCapabilities.TRANSPORT_VPN))key.append(network.toString()).append(";");
  }
  android.content.Intent battery=registerReceiver(null,new android.content.IntentFilter(Intent.ACTION_BATTERY_CHANGED));
  boolean low=false;
  if(battery!=null){int level=battery.getIntExtra(android.os.BatteryManager.EXTRA_LEVEL,100);
   int scale=battery.getIntExtra(android.os.BatteryManager.EXTRA_SCALE,100);
   low=battery.getIntExtra(android.os.BatteryManager.EXTRA_PLUGGED,0)==0&&level*100<=scale*20;}
  String signature=key.toString(); boolean saving=low;
  Backend.work.execute(()->Backend.module().callAttr("call","environment","["+org.json.JSONObject.quote(signature)+","+saving+"]"));
 }
 final Handler monitor=new Handler(android.os.Looper.getMainLooper());
 final Runnable poll=new Runnable(){public void run(){environment();monitor.postDelayed(this,10000);}};
 @Override public void onCreate(){
  super.onCreate();
  networks=new android.net.ConnectivityManager.NetworkCallback(){
   @Override public void onAvailable(android.net.Network n){environment();}
   @Override public void onLost(android.net.Network n){environment();}
  };
  getSystemService(android.net.ConnectivityManager.class).registerNetworkCallback(
   new android.net.NetworkRequest.Builder().addCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET)
    .addCapability(android.net.NetworkCapabilities.NET_CAPABILITY_NOT_VPN).build(),networks);
  monitor.post(poll);
 }
 public ParcelFileDescriptor openTunnel() throws Exception {
  return new Builder().setSession("Bridge").setMtu(1500)
   .addAddress("10.77.0.2",32).addAddress("fd77::2",128)
   .addRoute("0.0.0.0",0).addRoute("::",0).addDnsServer("1.1.1.1")
   .addDisallowedApplication(getPackageName()).establish();
 }
 @Override public int onStartCommand(Intent intent,int flags,int startId) {
  NotificationManager manager=getSystemService(NotificationManager.class);
  manager.createNotificationChannel(new NotificationChannel("vpn","Bridge VPN",NotificationManager.IMPORTANCE_LOW));
  PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE);
  startForeground(1,new Notification.Builder(this,"vpn").setContentTitle("Bridge")
   .setContentText("Bridge VPN").setSmallIcon(R.drawable.icon)
   .setContentIntent(open).setOngoing(true).build());
  if(intent!=null)Backend.work.execute(()->{
   ResultReceiver receiver=intent.getParcelableExtra("receiver");
   String result;
   try {result=Backend.module().callAttr("connect",this,intent.getStringExtra("name"),intent.getStringExtra("candidates")==null?"null":intent.getStringExtra("candidates")).toString();}
   catch(Exception e){result="{\"error\":\"Не удалось запустить VPN.\"}";}
   Bundle data=new Bundle();data.putString("result",result);
   if(receiver!=null)receiver.send(0,data);
   try {if(!new org.json.JSONObject(result).isNull("error"))stopSelf();}catch(Exception ignored){}
  });
  return START_NOT_STICKY;
 }
 @Override public void onRevoke(){stopSelf();}
 @Override public void onDestroy(){
  monitor.removeCallbacks(poll);
  if(networks!=null)getSystemService(android.net.ConnectivityManager.class).unregisterNetworkCallback(networks);
  Backend.work.execute(()->Backend.module().callAttr("call","disconnect","[]"));
  super.onDestroy();
 }
}
