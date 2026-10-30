package live.quehay.startup;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.ComponentName;
import android.content.Intent;
import android.graphics.Bitmap;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.WebView;
import android.widget.FrameLayout;
import java.io.File;
import java.io.FileOutputStream;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Dependency-free native checks; refuses to run against existing user packages. */
public final class StartupChecks extends Instrumentation {
    private Bundle args;
    private Activity activity;
    private FrameLayout root;
    private WebView web;
    private StartupOverlay overlay;
    private int passed;
    private long firstFrameMs;
    private long deadlineMs;
    @Override public void onCreate(Bundle arguments) { super.onCreate(arguments); args=arguments; start(); }
    private void check(boolean ok,String message) { if(!ok)throw new AssertionError(message); passed++; }
    private WebView findWeb(View v) {
        if(v instanceof WebView)return (WebView)v;
        if(v instanceof ViewGroup)for(int i=0;i<((ViewGroup)v).getChildCount();i++){
            WebView found=findWeb(((ViewGroup)v).getChildAt(i));if(found!=null)return found;
        }
        return null;
    }
    private boolean covered() {
        boolean[] value={false};runOnMainSync(()->value[0]=root.findViewWithTag("qh-startup")!=null);return value[0];
    }
    private void create(Bundle restored) {
        runOnMainSync(()->{int art=activity.getResources().getIdentifier("qh_startup_face","drawable",activity.getPackageName());overlay=new StartupOverlay(activity,root,restored,art);});
    }
    private long awaitClear(long limit) {
        long at=SystemClock.elapsedRealtime();while(covered()&&SystemClock.elapsedRealtime()-at<limit)SystemClock.sleep(20);
        return SystemClock.elapsedRealtime()-at;
    }
    private void shot(String name) throws Exception {
        Bitmap bmp=getUiAutomation().takeScreenshot();
        if(bmp==null)throw new AssertionError("No screenshot");
        File file=new File(getTargetContext().getExternalFilesDir(null),name);
        try(FileOutputStream out=new FileOutputStream(file)){bmp.compress(Bitmap.CompressFormat.PNG,100,out);}finally{bmp.recycle();}
    }
    @Override public void onStart() {
        Bundle result=new Bundle();
        try {
            String pkg=getTargetContext().getPackageName();
            if(!pkg.endsWith(".startupcheck"))throw new AssertionError("Isolated test package required");
            String className=pkg.contains(".tv.")?"live.quehay.tv.MainActivity":"live.quehay.app.MainActivity";
            activity=startActivitySync(new Intent().setComponent(new ComponentName(pkg,className)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            runOnMainSync(()->{root=(FrameLayout)((ViewGroup)activity.findViewById(android.R.id.content)).getChildAt(0);web=findWeb(root);});
            awaitClear(2600);check(!covered(),"Real activity startup remained blocked");
            check(web!=null,"WebView absent");
            String[] url={null};runOnMainSync(()->url[0]=web.getUrl());
            check(url[0]!=null&&url[0].startsWith("http://127.0.0.1:5031"),"Only local origin permitted");
            CountDownLatch pageReady=new CountDownLatch(1);String[] dom={null};
            runOnMainSync(()->web.evaluateJavascript("Boolean(document.getElementById('screen') || document.getElementById('contenido'))",v->{dom[0]=v;pageReady.countDown();}));
            check(pageReady.await(3,TimeUnit.SECONDS)&&"true".equals(dom[0]),"Local catalog document did not load");
            create(new Bundle());check(!covered(),"Restored activity replayed intro");
            create(null);check(covered(),"Fresh startup missing");
            SystemClock.sleep(100);shot("startup-100.png");SystemClock.sleep(400);shot("startup-500.png");
            runOnMainSync(()->overlay.dispose());check(!covered(),"Disposal must be immediate");
            runOnMainSync(()->CookieManager.getInstance().setCookie("http://127.0.0.1:5031","qh_startup_check=kept; Path=/"));
            create(null);long now=SystemClock.elapsedRealtime();runOnMainSync(()->overlay.firstFrame(web));awaitClear(1300);firstFrameMs=SystemClock.elapsedRealtime()-now;
            check(!covered()&&firstFrameMs<1300,"Ready page waited for the deadline");
            create(null);now=SystemClock.elapsedRealtime();awaitClear(2600);deadlineMs=SystemClock.elapsedRealtime()-now;
            check(!covered()&&deadlineMs<2600,"Slow page exceeded bounded cover");
            runOnMainSync(()->{overlay.firstFrame(web);overlay.dispose();});check(!covered(),"Late callback recreated cover");
            String[] cookie={null};runOnMainSync(()->cookie[0]=CookieManager.getInstance().getCookie("http://127.0.0.1:5031"));
            check(cookie[0]!=null&&cookie[0].contains("qh_startup_check=kept"),"Cookie lost");
            runOnMainSync(()->web.reload());SystemClock.sleep(1100);check(!covered(),"Navigation replayed introduction");
            shot("ready.png");
            result.putString("stream","PASS "+passed+" native checks; firstFrameMs="+firstFrameMs+"; deadlineMs="+deadlineMs+"\n");
            finish(Activity.RESULT_OK,result);
        } catch(Throwable error) {
            result.putString("stream","FAIL "+error.getClass().getSimpleName()+": "+error.getMessage()+"\n");
            finish(Activity.RESULT_CANCELED,result);
        } finally { if(activity!=null)runOnMainSync(()->activity.finish()); }
    }
}
