package app.bridge;
import android.app.*;
import android.content.*;
import android.net.VpnService;
import android.os.*;
public class TunnelService extends VpnService {
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
   try {result=Backend.module().callAttr("connect",this,intent.getStringExtra("name")).toString();}
   catch(Exception e){result="{\"error\":\"Не удалось запустить VPN.\"}";}
   Bundle data=new Bundle();data.putString("result",result);
   if(receiver!=null)receiver.send(0,data);
   if(result.contains("\"error\""))stopSelf();
  });
  return START_NOT_STICKY;
 }
 @Override public void onRevoke(){stopSelf();}
 @Override public void onDestroy(){
  Backend.work.execute(()->Backend.module().callAttr("call","disconnect","[]"));
  super.onDestroy();
 }
}
