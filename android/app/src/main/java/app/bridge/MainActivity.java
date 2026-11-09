package app.bridge;
import android.app.*;
import android.os.*;
import android.content.*;
import android.net.VpnService;
import android.webkit.*;
import org.json.*;

public class MainActivity extends Activity {
 WebView view;
 int pendingId;
 String pendingName;
 @Override public void onCreate(Bundle state) {
  super.onCreate(state);
  if(android.os.Build.VERSION.SDK_INT>=33 && checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=android.content.pm.PackageManager.PERMISSION_GRANTED)
   requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},2);
  Backend.module().callAttr("init", getFilesDir().toString());
  view=new WebView(this);
  view.getSettings().setJavaScriptEnabled(true);
  view.getSettings().setAllowFileAccess(false);
  view.getSettings().setAllowContentAccess(false);
  view.setWebViewClient(new WebViewClient() {
   @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) { return true; }
  });
  view.addJavascriptInterface(new Object() {
   @JavascriptInterface public void call(int id,String method,String args) {
    runOnUiThread(()->dispatch(id,method,args));
   }
  },"BridgeNative");
  android.widget.FrameLayout box=new android.widget.FrameLayout(this);
  box.setBackgroundColor(android.graphics.Color.rgb(23,28,25));
  box.addView(view,new android.widget.FrameLayout.LayoutParams(-1,-1));
  box.setOnApplyWindowInsetsListener((v,insets)->{
   v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),
                insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());
   return insets;
  });
  getWindow().getDecorView().setSystemUiVisibility(0);
  getWindow().setStatusBarColor(android.graphics.Color.rgb(23,28,25));
  getWindow().setNavigationBarColor(android.graphics.Color.rgb(23,28,25));
  view.setBackgroundColor(android.graphics.Color.rgb(23,28,25));
  setContentView(box);
  box.requestApplyInsets();
  try {
   java.io.ByteArrayOutputStream buffer=new java.io.ByteArrayOutputStream();
   try(java.io.InputStream input=getAssets().open("bridge.html")){
    byte[] chunk=new byte[8192]; int count;
    while((count=input.read(chunk))!=-1)buffer.write(chunk,0,count);
   }
   String html=buffer.toString("UTF-8");
   view.loadDataWithBaseURL("https://bridge.local/",html.replace("<html lang=\"ru\">","<html lang=\"ru\" class=\"android\">"),"text/html","UTF-8",null);
  } catch(Exception e) { finish(); }
 }
 void reply(int id,String result) {
  runOnUiThread(()->{ if(!isDestroyed())view.evaluateJavascript("bridgeReply("+id+","+result+")",null); });
 }
 void dispatch(int id,String method,String args) {
  try {
   if(method.equals("paste")) {
    ClipboardManager cm=(ClipboardManager)getSystemService(CLIPBOARD_SERVICE);
    CharSequence text=cm.hasPrimaryClip()?cm.getPrimaryClip().getItemAt(0).coerceToText(this):"";
    reply(id,new JSONObject().put("text",text.toString()).toString()); return;
   }
   if(method.equals("connect")) {
    pendingId=id;pendingName=new JSONArray(args).getString(0);
    Intent permission=VpnService.prepare(this);
    if(permission!=null)startActivityForResult(permission,1);else startTunnel();
    return;
   }
   if(method.equals("cancel")){
    new Thread(()->reply(id,Backend.module().callAttr("call","cancel","[]").toString())).start();
    return;
   }
   Backend.work.execute(()->{
    try { reply(id,Backend.module().callAttr("call",method,args).toString()); }
    catch(Exception e){reply(id,"{\"error\":\"Не удалось выполнить действие.\"}");}
    if(method.equals("disconnect")||method.equals("reset"))stopService(new Intent(this,TunnelService.class));
   });
  }catch(Exception e){reply(id,"{\"error\":\"Проверьте параметры.\"}");}
 }
 void startTunnel() {
  final int id=pendingId;
  ResultReceiver receiver=new ResultReceiver(new Handler(getMainLooper())) {
   @Override protected void onReceiveResult(int code,Bundle data) { reply(id,data.getString("result")); }
  };
  startForegroundService(new Intent(this,TunnelService.class).putExtra("name",pendingName).putExtra("receiver",receiver));
 }
 @Override public void onBackPressed() {
  Backend.work.execute(()->{
   try {
    org.json.JSONObject preferences=new org.json.JSONObject(Backend.module().callAttr("call","preferences","[]").toString());
    if(!preferences.optString("close_behavior","stop").equals("background")){
     Backend.module().callAttr("call","disconnect","[]");
     stopService(new Intent(this,TunnelService.class));
    }
   }catch(Exception ignored){}
   runOnUiThread(()->finish());
  });
 }
 @Override protected void onActivityResult(int request,int result,Intent data) {
  super.onActivityResult(request,result,data);
  if(request==1) { if(result==RESULT_OK)startTunnel();else reply(pendingId,"{\"error\":\"Разрешение VPN отклонено.\"}"); }
 }
}
