package live.quehay.tv;

import android.app.Activity;
import live.quehay.startup.StartupOverlay;
import android.app.AlertDialog;
import android.graphics.Color;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Bundle;
import android.os.Message;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.*;
import android.widget.*;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

/** Independent TV application: no bundled credentials or native JS bridge. */
public final class MainActivity extends Activity {
    private static final String ORIGIN=BuildConfig.TV_ORIGIN;
    private StartupOverlay startup;
    private WebView web;
    private FrameLayout root;
    private LinearLayout errorView;
    private ProgressBar progress;
    private View customView;
    private WebChromeClient.CustomViewCallback customCallback;
    private String remoteScript;
    private boolean destroyed;
    private boolean failed;

    private boolean firstParty(Uri uri) {
        Uri origin=Uri.parse(ORIGIN);
        return origin.getScheme().equals(uri.getScheme()) && origin.getHost().equals(uri.getHost())
            && origin.getPort()==uri.getPort() && uri.getUserInfo()==null
            && ("/tv".equals(uri.getPath()) || "/tv/".equals(uri.getPath()));
    }
    private boolean onOurPage(){return web.getUrl()!=null && firstParty(Uri.parse(web.getUrl()));}
    private String asset(String name){
        try(var stream=getAssets().open(name);var out=new ByteArrayOutputStream()){
            byte[] bytes=new byte[4096];int n;while((n=stream.read(bytes))!=-1)out.write(bytes,0,n);
            return out.toString(StandardCharsets.UTF_8.name());
        }catch(IOException e){throw new IllegalStateException("Falta el control de TV",e);}
    }
    @Override public void onCreate(Bundle state){
        super.onCreate(state);remoteScript=asset("remote.js");
        root=new FrameLayout(this);root.setBackgroundColor(Color.rgb(7,14,24));setContentView(root);
        web=new WebView(this);web.setBackgroundColor(Color.rgb(7,14,24));web.setFocusable(true);web.setFocusableInTouchMode(true);
        root.addView(web,new FrameLayout.LayoutParams(-1,-1));
        progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);
        root.addView(progress,new FrameLayout.LayoutParams(-1,4,Gravity.TOP));
        WebSettings s=web.getSettings();s.setJavaScriptEnabled(true);s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);s.setAllowContentAccess(false);s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setMediaPlaybackRequiresUserGesture(true);s.setSafeBrowsingEnabled(true);
        s.setSupportMultipleWindows(true);s.setJavaScriptCanOpenWindowsAutomatically(false);
        s.setUserAgentString(s.getUserAgentString()+" QueHayTV/"+BuildConfig.VERSION_NAME);
        CookieManager.getInstance().setAcceptCookie(true);CookieManager.getInstance().setAcceptThirdPartyCookies(web,false);
        WebView.setWebContentsDebuggingEnabled(false);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest req){
                // Provider frames can navigate over HTTPS, but never replace the TV app.
                if(!req.isForMainFrame())return !"https".equals(req.getUrl().getScheme());
                return !firstParty(req.getUrl());
            }
            @Override public void onPageStarted(WebView v,String url,android.graphics.Bitmap icon){failed=false;hideError();progress.setVisibility(View.VISIBLE);}
            @Override public void onPageCommitVisible(WebView v,String url){
                if(startup!=null && firstParty(Uri.parse(url)))startup.firstFrame(v);
            }
            @Override public void onPageFinished(WebView v,String url){
                progress.setVisibility(View.GONE);
                if(onOurPage()&&!failed){web.evaluateJavascript(remoteScript,null);CookieManager.getInstance().flush();web.requestFocus();}
            }
            @Override public void onReceivedError(WebView v,WebResourceRequest req,WebResourceError e){if(req.isForMainFrame())showError();}
            @Override public void onReceivedHttpError(WebView v,WebResourceRequest req,WebResourceResponse r){if(req.isForMainFrame()&&r.getStatusCode()>=400)showError();}
            @Override public void onReceivedSslError(WebView v,SslErrorHandler h,SslError e){h.cancel();}
            @Override public boolean onRenderProcessGone(WebView v,RenderProcessGoneDetail d){
                destroyed=true;if(startup!=null)startup.dispose();root.removeView(web);web.destroy();
                new AlertDialog.Builder(MainActivity.this).setMessage("El reproductor se cerró. Vuelve a abrir Qué Hay TV.")
                    .setPositiveButton("Cerrar",(dialog,which)->finish()).setCancelable(false).show();return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public void onProgressChanged(WebView v,int value){progress.setProgress(value);}
            @Override public void onPermissionRequest(PermissionRequest req){req.deny();}
            @Override public boolean onCreateWindow(WebView v,boolean dialog,boolean gesture,Message result){return false;}
            @Override public void onShowCustomView(View v,CustomViewCallback cb){
                if(customView!=null){cb.onCustomViewHidden();return;}
                customView=v;customCallback=cb;web.setVisibility(View.GONE);root.addView(v,new FrameLayout.LayoutParams(-1,-1));v.requestFocus();immersive();
            }
            @Override public void onHideCustomView(){hideCustom();}
        });
        // This TV package deliberately has no download flow or external browser intents.
        web.setDownloadListener((url,ua,disposition,mime,length)->{});
        startup = new StartupOverlay(this, root, state, R.drawable.qh_startup_face);
        immersive();web.requestFocus();web.loadUrl(ORIGIN+"/tv");
    }
    private String remoteKey(int code){
        switch(code){case KeyEvent.KEYCODE_DPAD_UP:return "ArrowUp";case KeyEvent.KEYCODE_DPAD_DOWN:return "ArrowDown";
            case KeyEvent.KEYCODE_DPAD_LEFT:return "ArrowLeft";case KeyEvent.KEYCODE_DPAD_RIGHT:return "ArrowRight";
            case KeyEvent.KEYCODE_DPAD_CENTER:case KeyEvent.KEYCODE_ENTER:return "Enter";default:return null;}
    }
    @Override public boolean dispatchKeyEvent(KeyEvent event){
        String key=remoteKey(event.getKeyCode());
        if(key!=null && customView==null && errorView==null && !destroyed && web!=null && web.hasFocus() && onOurPage()){
            KeyEvent copy=new KeyEvent(event);
            web.evaluateJavascript("Boolean(window.QueHayTVRemote && window.QueHayTVRemote("+JSONObject.quote(key)+","+(event.getAction()==KeyEvent.ACTION_UP)+"))",handled->{
                // Native WebView events retain player controls and text-entry behavior.
                if(!destroyed && !"true".equals(handled))web.dispatchKeyEvent(copy);
            });return true;
        }
        return super.dispatchKeyEvent(event);
    }
    private void immersive(){
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        if(android.os.Build.VERSION.SDK_INT>=30){
            var c=getWindow().getInsetsController();if(c!=null){c.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);c.hide(WindowInsets.Type.systemBars());}
        }else root.setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
    }
    private void hideCustom(){if(customView!=null){root.removeView(customView);customView=null;customCallback.onCustomViewHidden();customCallback=null;web.setVisibility(View.VISIBLE);web.requestFocus();immersive();}}
    private void hideError(){if(errorView!=null){root.removeView(errorView);errorView=null;}}
    private void showError(){
        if(startup!=null)startup.dispose();
        failed=true;progress.setVisibility(View.GONE);if(errorView!=null)return;
        errorView=new LinearLayout(this);errorView.setOrientation(LinearLayout.VERTICAL);errorView.setGravity(Gravity.CENTER);errorView.setPadding(40,30,40,30);errorView.setBackgroundColor(Color.rgb(7,14,24));
        TextView title=new TextView(this);title.setText(BuildConfig.LIVE ? "No pudimos conectar con Qué Hay" : "Conecta con tu PC de prueba");title.setTextColor(Color.WHITE);title.setTextSize(24);errorView.addView(title);
        TextView text=new TextView(this);text.setText(BuildConfig.LIVE ? "Comprueba la conexión a internet del televisor y vuelve a intentarlo." : "La PC debe estar encendida y en la misma red que el televisor.\nServidor: "+ORIGIN);text.setTextColor(Color.LTGRAY);text.setGravity(Gravity.CENTER);text.setPadding(0,20,0,20);errorView.addView(text);
        Button retry=new Button(this);retry.setText("Volver a intentar");retry.setOnClickListener(v->{hideError();web.requestFocus();web.loadUrl(ORIGIN+"/tv");});errorView.addView(retry);
        root.addView(errorView,new FrameLayout.LayoutParams(-1,-1));retry.requestFocus();
    }
    @Override public void onBackPressed(){
        if(startup!=null)startup.dispose();
        if(customView!=null){hideCustom();return;}
        if(!destroyed && errorView==null && onOurPage())web.evaluateJavascript("Boolean(window.TVBack && window.TVBack())",handled->{if(!"true".equals(handled))confirmExit();});
        else confirmExit();
    }
    private void confirmExit(){new AlertDialog.Builder(this).setMessage("¿Salir de Qué Hay TV?").setNegativeButton("Seguir aquí",null).setPositiveButton("Salir",(d,w)->finish()).show();}
    @Override protected void onPause(){if(startup!=null)startup.dispose();if(web!=null&&!destroyed){CookieManager.getInstance().flush();web.onPause();}super.onPause();}
    @Override protected void onResume(){super.onResume();if(web!=null&&!destroyed){web.onResume();immersive();}}
    @Override protected void onDestroy(){if(startup!=null)startup.dispose();if(web!=null&&!destroyed){destroyed=true;web.stopLoading();web.destroy();}super.onDestroy();}
}
