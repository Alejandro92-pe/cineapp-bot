package live.quehay.app;

import android.graphics.Insets;
import android.os.Build;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;

/** The native container owns safe space; WebView must not reserve it again. */
final class MobileInsets {
    private MobileInsets() {}
    @SuppressWarnings("deprecation")
    static final int LEGACY_LAYOUT_FLAGS = View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION;

    @SuppressWarnings("deprecation")
    static void configureWindow(Window window) {
        // Make the container's geometry consistent before/after Android 15's
        // enforced edge-to-edge. Otherwise older versions can fit it twice.
        if (Build.VERSION.SDK_INT >= 30) window.setDecorFitsSystemWindows(false);
        else window.getDecorView().setSystemUiVisibility(LEGACY_LAYOUT_FLAGS);
    }

    @SuppressWarnings("deprecation")
    static WindowInsets apply(View view, WindowInsets insets) {
        if (Build.VERSION.SDK_INT >= 30) {
            int bars = WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout();
            int handled = bars | WindowInsets.Type.ime();
            Insets safe = insets.getInsets(handled);
            view.setPadding(safe.left, safe.top, safe.right, safe.bottom);
            // Deliver zero values, not CONSUMED: WebView still needs notifications
            // when the keyboard closes or fullscreen restores the system bars.
            return new WindowInsets.Builder(insets).setInsets(handled, Insets.NONE)
                .setInsetsIgnoringVisibility(bars, Insets.NONE).setDisplayCutout(null).build();
        }
        int left=insets.getSystemWindowInsetLeft(), top=insets.getSystemWindowInsetTop();
        int right=insets.getSystemWindowInsetRight(), bottom=insets.getSystemWindowInsetBottom();
        if (Build.VERSION.SDK_INT >= 28 && insets.getDisplayCutout()!=null) {
            var cutout=insets.getDisplayCutout();
            left=Math.max(left,cutout.getSafeInsetLeft()); top=Math.max(top,cutout.getSafeInsetTop());
            right=Math.max(right,cutout.getSafeInsetRight()); bottom=Math.max(bottom,cutout.getSafeInsetBottom());
        }
        view.setPadding(left,top,right,bottom);
        WindowInsets remaining=insets.replaceSystemWindowInsets(0,0,0,0).consumeStableInsets();
        return Build.VERSION.SDK_INT >= 28 ? remaining.consumeDisplayCutout() : remaining;
    }
}
