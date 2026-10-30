package live.quehay.startup;

import android.animation.ValueAnimator;
import android.app.Activity;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.animation.DecelerateInterpolator;
import android.webkit.WebView;
import android.widget.FrameLayout;
import android.widget.ImageView;

/** One cold-activity introduction, entirely local and independent of accounts.
 * Never delays a request or waits for the animation to finish before revealing UI.
 */
public final class StartupOverlay {
    private static final long MAX_COVER_MS = 1800;
    private static final long EXIT_MS = 100;
    private final FrameLayout root;
    private FrameLayout cover;
    private ImageView face;
    private boolean closed;
    private boolean visualRequested;
    private final Runnable deadline = () -> dismiss(false);

    public StartupOverlay(Activity activity, FrameLayout root, Bundle restored, int artwork) {
        this.root = root;
        // Android 12+ supplies its own launch window; remove it without adding
        // another exit animation or a forced minimum display duration.
        if (Build.VERSION.SDK_INT >= 31) {
            activity.getSplashScreen().setOnExitAnimationListener(view -> view.remove());
        }
        if (restored != null) { closed = true; return; }
        cover = new FrameLayout(activity);
        cover.setTag("qh-startup");
        cover.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
        cover.setFocusable(false);
        cover.setBackground(new GradientDrawable(GradientDrawable.Orientation.TR_BL,
                new int[]{Color.rgb(21, 43, 65), Color.rgb(8, 15, 25), Color.rgb(8, 15, 25)}));
        face = new ImageView(activity);
        face.setImageResource(artwork);
        face.setScaleType(ImageView.ScaleType.FIT_CENTER);
        int size = Math.round(92 * activity.getResources().getDisplayMetrics().density);
        cover.addView(face, new FrameLayout.LayoutParams(size, size, Gravity.CENTER));
        root.addView(cover, new FrameLayout.LayoutParams(-1, -1));
        if (ValueAnimator.areAnimatorsEnabled()) {
            face.setAlpha(.35f); face.setScaleX(.88f); face.setScaleY(.88f); face.setRotation(-6f);
            face.animate().alpha(1f).scaleX(1f).scaleY(1f).rotation(0f)
                    .setDuration(650).setInterpolator(new DecelerateInterpolator()).start();
        }
        // A maximum, not a minimum. Slow/offline pages expose normal loading/error UI.
        root.postDelayed(deadline, MAX_COVER_MS);
    }

    public void firstFrame(WebView web) {
        if (closed || visualRequested) return;
        visualRequested = true;
        web.postVisualStateCallback(0, new WebView.VisualStateCallback() {
            @Override public void onComplete(long requestId) { dismiss(true); }
        });
    }

    public void dismiss(boolean fade) {
        if (closed) return;
        closed = true;
        root.removeCallbacks(deadline);
        if (face != null) face.animate().cancel();
        if (cover == null) return;
        if (fade && ValueAnimator.areAnimatorsEnabled()) {
            cover.animate().alpha(0f).setDuration(EXIT_MS).withEndAction(this::remove).start();
        } else remove();
    }

    private void remove() {
        if (cover != null) { cover.animate().cancel(); root.removeView(cover); cover = null; }
        face = null;
    }

    /** Called on pause/error/destruction as well as navigation away from launch. */
    public void dispose() { dismiss(false); remove(); }
}
