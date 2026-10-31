package live.quehay.app;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.ComponentName;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Insets;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.view.MotionEvent;
import android.view.inputmethod.InputMethodManager;
import android.webkit.CookieManager;
import android.webkit.WebView;
import org.json.JSONObject;
import org.json.JSONTokener;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Runs exclusively in the isolated local-origin mobile package, never real accounts. */
public final class MobileInsetsChecks extends Instrumentation {
    private Activity activity;
    private ViewGroup root;
    private WebView web;
    private boolean baseline;
    private int passed;
    private final JSONObject result=new JSONObject();
    @Override public void onCreate(Bundle args) {
        baseline=args!=null && "true".equals(args.getString("baseline")); super.onCreate(args);start();
    }
    private void check(boolean value,String message) {if(!value)throw new AssertionError(message);passed++;}
    private WebView find(View view) {
        if(view instanceof WebView)return (WebView)view;
        if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++){
            WebView found=find(((ViewGroup)view).getChildAt(i));if(found!=null)return found;
        }
        return null;
    }
    private Object js(String code) throws Exception {
        CountDownLatch ready=new CountDownLatch(1);String[] output={null};
        runOnMainSync(()->web.evaluateJavascript(code,v->{output[0]=v;ready.countDown();}));
        check(ready.await(5,TimeUnit.SECONDS),"JavaScript timeout");
        return new JSONTokener(output[0]).nextValue();
    }
    private JSONObject geometry() throws Exception {
        JSONObject value=new JSONObject((String)js("JSON.stringify((()=>{const n=document.querySelector('.cine-mobile-nav'),s=n&&getComputedStyle(n),r=n&&n.getBoundingClientRect();return {width:innerWidth,height:innerHeight,visualHeight:visualViewport.height,navHeight:r&&r.height,navBottom:r&&r.bottom,navPaddingBottom:s&&parseFloat(s.paddingBottom),icons:n&&n.children.length,ua:navigator.userAgent}})())"));
        int[] dims=new int[9];
        runOnMainSync(()->{int[] xy=new int[2];web.getLocationOnScreen(xy);dims[0]=xy[0];dims[1]=xy[1];dims[2]=web.getWidth();dims[3]=web.getHeight();dims[4]=root.getPaddingBottom();dims[5]=root.getPaddingTop();dims[6]=root.getHeight();WindowInsets i=activity.getWindow().getDecorView().getRootWindowInsets();dims[7]=i.getInsets(WindowInsets.Type.systemBars()).bottom;dims[8]=i.getInsets(WindowInsets.Type.ime()).bottom;});
        value.put("webX",dims[0]).put("webY",dims[1]).put("webWidth",dims[2]).put("webHeight",dims[3]).put("nativeBottom",dims[4]).put("nativeTop",dims[5]).put("rootHeight",dims[6]).put("systemBottom",dims[7]).put("keyboardBottom",dims[8]);
        return value;
    }
    private void screenshot(String name) throws Exception {
        Bitmap bmp=getUiAutomation().takeScreenshot();check(bmp!=null,"Screenshot unavailable");
        try(FileOutputStream stream=new FileOutputStream(new File(getTargetContext().getExternalFilesDir(null),name))){bmp.compress(Bitmap.CompressFormat.PNG,100,stream);}finally{bmp.recycle();}
    }
    private void settle() {waitForIdleSync();SystemClock.sleep(700);}
    private void immersive(boolean value) {
        runOnMainSync(()->{try{var method=activity.getClass().getDeclaredMethod("applyImmersive",boolean.class);method.setAccessible(true);method.invoke(activity,value);}catch(Exception e){throw new RuntimeException(e);}});settle();
    }
    @Override public void onStart() {
        Bundle reply=new Bundle();
        try {
            check("live.quehay.app.startupcheck".equals(getTargetContext().getPackageName()),"Local isolated package required");
            activity=startActivitySync(new Intent().setComponent(new ComponentName(getTargetContext().getPackageName(),"live.quehay.app.MainActivity")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            runOnMainSync(()->{root=(ViewGroup)((ViewGroup)activity.findViewById(android.R.id.content)).getChildAt(0);web=find(root);});
            check(web!=null,"WebView missing");
            long deadline=SystemClock.elapsedRealtime()+20000;
            while(!Boolean.TRUE.equals(js("document.readyState==='complete' && !!document.querySelector('.cine-mobile-nav') && getComputedStyle(document.querySelector('.cine-mobile-nav')).position==='fixed'")) && SystemClock.elapsedRealtime()<deadline)SystemClock.sleep(300);
            String[] url={null};runOnMainSync(()->url[0]=web.getUrl());
            check(url[0]!=null && url[0].startsWith("http://127.0.0.1:5031/"),"Refusing non-local page");settle();
            JSONObject normal=geometry();result.put("normal",normal);screenshot(baseline?"before.png":"after.png");
            check(normal.getInt("icons")==4,"Expected the four existing navigation items");
            if(!baseline) {
                check(normal.getDouble("navPaddingBottom")<=8.5,"Safe area counted twice in bottom navigation");
                check(normal.getDouble("navHeight")<70,"Navigation unexpectedly tall");
                check(normal.getInt("nativeBottom")==normal.getInt("systemBottom"),"Native bottom must equal one system inset");
                runOnMainSync(()->{
                    View fixture=new View(activity);
                    int bars=WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout();
                    WindowInsets input=new WindowInsets.Builder().setInsets(bars,Insets.of(12,32,14,48)).setInsets(WindowInsets.Type.ime(),Insets.of(0,0,0,300)).build();
                    WindowInsets child=MobileInsets.apply(fixture,input);
                    check(fixture.getPaddingBottom()==300,"Keyboard must use max, not sum");
                    check(fixture.getPaddingLeft()==12 && fixture.getPaddingTop()==32 && fixture.getPaddingRight()==14,"Cutout or bars lost");
                    check(child.getInsets(bars|WindowInsets.Type.ime()).equals(Insets.NONE),"Handled insets forwarded twice");
                    child=MobileInsets.apply(fixture,new WindowInsets.Builder(input).setInsets(WindowInsets.Type.ime(),Insets.NONE).build());
                    check(fixture.getPaddingBottom()==48 && child.getInsets(WindowInsets.Type.ime()).bottom==0,"Ghost keyboard margin");
                    MobileInsets.apply(fixture,new WindowInsets.Builder().build());check(fixture.getPaddingBottom()==0,"Fullscreen margin remained");
                });
            }
            String[] cookie={null};runOnMainSync(()->cookie[0]=CookieManager.getInstance().getCookie("http://127.0.0.1:5031"));
            if(!baseline)check(cookie[0]!=null&&cookie[0].contains("qh_insets=kept"),"Cookie lost across install-r");
            else runOnMainSync(()->{CookieManager.getInstance().setCookie("http://127.0.0.1:5031","qh_insets=kept; Path=/");CookieManager.getInstance().flush();});
            if(baseline)js("localStorage.setItem('qh_insets_download','https://www.mediafire.com/file/local-fixture');true");
            else check("https://www.mediafire.com/file/local-fixture".equals(js("localStorage.getItem('qh_insets_download')")),"Stored data lost across upgrade");
            js("(()=>{let i=document.createElement('input');i.id='insets-keyboard';i.placeholder='Prueba local del teclado';i.style='position:fixed;top:100px;left:16px;width:250px;z-index:999999;background:white;color:black';document.body.append(i);i.focus();return true})()");
            settle();
            int[] position=new int[2];runOnMainSync(()->{web.requestFocus();web.getLocationOnScreen(position);});
            float density=activity.getResources().getDisplayMetrics().density;
            long tap=SystemClock.uptimeMillis();
            sendPointerSync(MotionEvent.obtain(tap,tap,MotionEvent.ACTION_DOWN,position[0]+100*density,position[1]+110*density,0));
            sendPointerSync(MotionEvent.obtain(tap,tap+70,MotionEvent.ACTION_UP,position[0]+100*density,position[1]+110*density,0));settle();
            runOnMainSync(()->((InputMethodManager)activity.getSystemService(Activity.INPUT_METHOD_SERVICE)).showSoftInput(web,InputMethodManager.SHOW_IMPLICIT));settle();
            JSONObject keyboard=geometry();result.put("keyboard",keyboard);screenshot(baseline?"before-keyboard.png":"after-keyboard.png");
            check(keyboard.getInt("keyboardBottom")>0,"Keyboard did not open");
            if(!baseline)check(Math.abs(keyboard.getDouble("height")-keyboard.getDouble("visualHeight"))<2,"Keyboard resized WebView twice");
            runOnMainSync(()->((InputMethodManager)activity.getSystemService(Activity.INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(web.getWindowToken(),0));js("document.getElementById('insets-keyboard').remove();true");settle();
            JSONObject closed=geometry();result.put("keyboardClosed",closed);
            check(Math.abs(normal.getDouble("navHeight")-closed.getDouble("navHeight"))<1,"Navigation retained keyboard space");
            immersive(true);result.put("fullscreen",geometry());screenshot(baseline?"before-fullscreen.png":"after-fullscreen.png");
            if(!baseline)check(root.getPaddingBottom()==0,"System bar padding remained in immersive mode");
            immersive(false);runOnMainSync(()->activity.setRequestedOrientation(android.content.pm.ActivityInfo.SCREEN_ORIENTATION_PORTRAIT));settle();
            JSONObject restored=geometry();result.put("restored",restored);screenshot(baseline?"before-restored.png":"after-restored.png");
            check(Math.abs(normal.getDouble("navHeight")-restored.getDouble("navHeight"))<1,"Fullscreen return changed navigation height");
            result.put("passed",passed).put("baseline",baseline).put("android",android.os.Build.VERSION.RELEASE);
            try(FileOutputStream file=new FileOutputStream(new File(getTargetContext().getExternalFilesDir(null),baseline?"before.json":"after.json"))){file.write(result.toString(2).getBytes(StandardCharsets.UTF_8));}
            reply.putString("stream","PASS "+passed+" checks; "+result.toString()+"\n");finish(Activity.RESULT_OK,reply);
        }catch(Throwable e){reply.putString("stream","FAIL "+e+"; "+result.toString()+"\n");finish(Activity.RESULT_CANCELED,reply);}
        finally{if(activity!=null)runOnMainSync(()->activity.finish());}
    }
}
