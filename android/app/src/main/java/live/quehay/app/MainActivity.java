package live.quehay.app;

import android.app.Activity;
import live.quehay.startup.StartupOverlay;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.graphics.Color;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Bundle;
import android.os.Message;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.*;
import android.widget.*;
import org.json.JSONObject;
import java.io.IOException;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;

/** Thin first-party shell. Provider frames never receive a JavaScript bridge. */
public final class MainActivity extends Activity {
    private static final String ORIGIN = BuildConfig.APP_ORIGIN;
    private StartupOverlay startup;
    private WebView web;
    private FrameLayout root;
    private LinearLayout errorView;
    private ProgressBar progress;
    private View customView;
    private WebChromeClient.CustomViewCallback customCallback;
    private boolean expanded;
    private String lastPage = ORIGIN + "/";

    static boolean isFirstParty(Uri uri) {
        Uri origin = Uri.parse(ORIGIN);
        return origin.getScheme().equals(uri.getScheme()) && origin.getHost().equals(uri.getHost())
            && uri.getUserInfo() == null && (uri.getPort() == origin.getPort()
                || ("https".equals(origin.getScheme()) && origin.getPort() == -1 && uri.getPort() == 443));
    }
    private boolean onOurPage() { return web.getUrl() != null && isFirstParty(Uri.parse(web.getUrl())); }
    private String asset(String name) {
        try (var stream = getAssets().open(name); var output=new ByteArrayOutputStream()) {
            byte[] buffer=new byte[8192];int length;
            while((length=stream.read(buffer))!=-1)output.write(buffer,0,length);
            return output.toString(StandardCharsets.UTF_8.name());
        }
        catch (IOException error) { throw new IllegalStateException("Falta un recurso de la aplicación", error); }
    }
    private void inject() {
        if (!onOurPage()) return;
        String css = JSONObject.quote(asset("mobile.css")+"\n"+asset("identity.css"));
        web.evaluateJavascript("(()=>{let s=document.getElementById('quehay-android-style');if(!s){s=document.createElement('style');s.id='quehay-android-style';document.head.append(s);}s.textContent="+css+";})();", null);
        web.evaluateJavascript(asset("share.js"), null);
        web.evaluateJavascript(asset("mobile.js"), null);
        web.evaluateJavascript(asset("identity.js"), null);
    }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        MobileInsets.configureWindow(getWindow());
        root = new FrameLayout(this); root.setBackgroundColor(Color.rgb(8,15,25)); setContentView(root);
        web = new WebView(this); web.setBackgroundColor(Color.rgb(8,15,25));
        root.addView(web,new FrameLayout.LayoutParams(-1,-1));
        progress = new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);
        root.addView(progress,new FrameLayout.LayoutParams(-1,6,Gravity.TOP));
        root.setOnApplyWindowInsetsListener(MobileInsets::apply);
        root.requestApplyInsets();
        WebSettings settings=web.getSettings();
        settings.setJavaScriptEnabled(true); settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false); settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setSupportMultipleWindows(true); settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setUserAgentString(settings.getUserAgentString()+" QueHayAndroid/"+BuildConfig.VERSION_NAME);
        settings.setSafeBrowsingEnabled(true);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web,false);
        // No debugging ports, native interfaces, embedded credentials or SSL bypass.
        WebView.setWebContentsDebuggingEnabled(false);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request) {
                Uri uri=request.getUrl();
                if(!request.isForMainFrame())return !"https".equals(uri.getScheme());
                if("quehay-app".equals(uri.getScheme())) {
                    if(onOurPage() && request.hasGesture()) {
                        if("fullscreen".equals(uri.getHost()))toggleExpanded();
                        else if("share".equals(uri.getHost()))shareTitle(uri);
                    }
                    return true;
                }
                if(isFirstParty(uri))return false;
                if(request.hasGesture())openExternal(uri);
                return true;
            }
            @Override public void onPageStarted(WebView view,String url,android.graphics.Bitmap icon) {
                if(isFirstParty(Uri.parse(url))){lastPage=url;hideError();progress.setVisibility(View.VISIBLE);}
            }
            @Override public void onPageCommitVisible(WebView view,String url) {
                if(startup!=null && isFirstParty(Uri.parse(url)))startup.firstFrame(view);
            }
            @Override public void onPageFinished(WebView view,String url) {
                progress.setVisibility(View.GONE);inject();CookieManager.getInstance().flush();
            }
            @Override public void onReceivedSslError(WebView view,SslErrorHandler handler,SslError error) { handler.cancel(); }
            @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error) {
                if(request.isForMainFrame())showError(); else providerFailure(request.getUrl().toString());
            }
            @Override public void onReceivedHttpError(WebView view,WebResourceRequest request,WebResourceResponse response) {
                if(request.isForMainFrame() && response.getStatusCode()>=500)showError();
                else if(response.getStatusCode()==404 || response.getStatusCode()>=500)providerFailure(request.getUrl().toString());
            }
            @Override public boolean onRenderProcessGone(WebView view,RenderProcessGoneDetail detail) {
                if(startup!=null)startup.dispose();root.removeView(web);web.destroy();new AlertDialog.Builder(MainActivity.this).setMessage("El reproductor se cerró. Vuelve a abrir Qué Hay para continuar.").setPositiveButton("Cerrar",(d,w)->finish()).setCancelable(false).show();return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public void onProgressChanged(WebView view,int value){progress.setProgress(value);}
            @Override public void onPermissionRequest(PermissionRequest request){request.deny();}
            @Override public void onShowCustomView(View view,CustomViewCallback callback){
                if(customView!=null){callback.onCustomViewHidden();return;}
                customView=view;customCallback=callback;root.addView(view,new FrameLayout.LayoutParams(-1,-1));applyImmersive(true);
            }
            @Override public void onHideCustomView(){hideCustom();}
            @Override public boolean onCreateWindow(WebView view,boolean dialog,boolean gesture,Message result){
                if(!gesture)return false;
                WebView popup=new WebView(MainActivity.this);
                popup.setWebViewClient(new WebViewClient(){
                    @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest request){
                        openExternal(request.getUrl());popup.destroy();return true;
                    }
                });
                ((WebView.WebViewTransport)result.obj).setWebView(popup);result.sendToTarget();return true;
            }
        });
        web.setDownloadListener((url,userAgent,disposition,mime,length)->openExternal(Uri.parse(url)));
        startup = new StartupOverlay(this, root, state, R.drawable.qh_startup_face);
        if(state==null || web.restoreState(state)==null)web.loadUrl(lastPage);
    }
    private void providerFailure(String url){
        if(onOurPage())web.post(()->web.evaluateJavascript("window.QueHayAndroidUI?.providerFailure("+JSONObject.quote(url)+");",null));
    }
    private void openExternal(Uri uri){
        if(!"https".equals(uri.getScheme()) || uri.getHost()==null || uri.getUserInfo()!=null)return;
        try{startActivity(new Intent(Intent.ACTION_VIEW,uri).addCategory(Intent.CATEGORY_BROWSABLE));}
        catch(android.content.ActivityNotFoundException e){Toast.makeText(this,"Instala un navegador para abrir este enlace.",Toast.LENGTH_LONG).show();}
    }
    private void shareTitle(Uri uri){
        String id=uri.getQueryParameter("id"), title=uri.getQueryParameter("title");
        if(id==null || !id.matches("[1-9][0-9]{0,18}") || title==null)return;
        title=title.replaceAll("[\\p{Cntrl}]"," ").trim();
        if(title.isEmpty() || title.length()>200)return;
        String text="🎬 Mira «"+title+"» en Qué Hay Cine.\n"+ORIGIN+"/?contenido="+id;
        Intent send=new Intent(Intent.ACTION_SEND).setType("text/plain");
        send.putExtra(Intent.EXTRA_SUBJECT,title);send.putExtra(Intent.EXTRA_TEXT,text);
        try{startActivity(Intent.createChooser(send,"Compartir película o serie"));}
        catch(android.content.ActivityNotFoundException error){Toast.makeText(this,"No hay aplicaciones disponibles para compartir.",Toast.LENGTH_LONG).show();}
    }
    private void showError(){
        if(startup!=null)startup.dispose();
        if(errorView!=null)return;
        errorView=new LinearLayout(this);errorView.setOrientation(LinearLayout.VERTICAL);errorView.setGravity(Gravity.CENTER);errorView.setPadding(40,40,40,40);errorView.setBackgroundColor(Color.rgb(8,15,25));
        TextView title=new TextView(this);title.setText("Volvemos en un momento");title.setTextColor(Color.WHITE);title.setTextSize(24);errorView.addView(title);
        TextView text=new TextView(this);text.setText("Revisa tu conexión y vuelve a intentarlo. Tu cuenta sigue guardada.");text.setTextColor(Color.LTGRAY);text.setPadding(0,25,0,25);errorView.addView(text);
        Button retry=new Button(this);retry.setText("Volver a intentar");retry.setOnClickListener(v->{hideError();web.loadUrl(lastPage);});errorView.addView(retry);root.addView(errorView,new FrameLayout.LayoutParams(-1,-1));
    }
    private void hideError(){if(errorView!=null){root.removeView(errorView);errorView=null;}}
    private void toggleExpanded(){expanded=!expanded;applyImmersive(expanded);web.evaluateJavascript("window.QueHayAndroidUI?.fullscreen("+expanded+");",null);}
    private void applyImmersive(boolean value){
        if(value)getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        if(android.os.Build.VERSION.SDK_INT>=30){
            var controller=getWindow().getInsetsController();
            if(controller!=null){controller.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);if(value)controller.hide(WindowInsets.Type.systemBars());else controller.show(WindowInsets.Type.systemBars());}
        }else root.setSystemUiVisibility(MobileInsets.LEGACY_LAYOUT_FLAGS | (value ? View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY : 0));
        setRequestedOrientation(value ? ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE : ActivityInfo.SCREEN_ORIENTATION_FULL_USER);
    }
    private void hideCustom(){if(customView!=null){root.removeView(customView);customView=null;customCallback.onCustomViewHidden();customCallback=null;applyImmersive(expanded);}}
    @Override public void onBackPressed(){
        if(startup!=null)startup.dispose();
        if(customView!=null){hideCustom();return;}if(expanded){toggleExpanded();return;}
        web.evaluateJavascript("Boolean(window.QueHayAndroidUI?.back())",handled->{if(!"true".equals(handled)){if(web.canGoBack())web.goBack();else new AlertDialog.Builder(this).setMessage("¿Salir de Qué Hay?").setNegativeButton("Seguir aquí",null).setPositiveButton("Salir",(d,w)->finish()).show();}});
    }
    @Override protected void onSaveInstanceState(Bundle state){web.saveState(state);super.onSaveInstanceState(state);}
    @Override protected void onPause(){if(startup!=null)startup.dispose();CookieManager.getInstance().flush();web.onPause();super.onPause();}
    @Override protected void onResume(){super.onResume();if(web!=null)web.onResume();}
    @Override protected void onDestroy(){if(startup!=null)startup.dispose();if(web!=null){web.stopLoading();web.destroy();}super.onDestroy();}
}
