# Salon De Nature PWA

## Included

- Web app manifest at `/manifest.webmanifest`
- Root-scoped service worker at `/service-worker.js`
- Install icons in 192px, 512px, and maskable 512px formats
- Android/Chromium install prompt
- iPhone/iPad Safari “Add to Home Screen” guidance
- Offline fallback page

## Cache policy

Only static same-origin assets are cached. API responses, administrator pages, staff pages, customer reservation pages, and navigated HTML responses are not stored. When navigation fails, the service worker returns the generic offline page.

## Production requirements

- HTTPS must remain enabled.
- `/service-worker.js` must be served from the site root with `Service-Worker-Allowed: /`.
- Do not configure Nginx to aggressively cache `/service-worker.js`.
- After deployment, restart Gunicorn and hard-refresh the browser once.

## Verification

Open these URLs:

```text
https://salondenature.shop/manifest.webmanifest
https://salondenature.shop/service-worker.js
https://salondenature.shop/offline
```

In Chrome DevTools, check **Application → Manifest** and **Application → Service Workers**. On Android Chrome, use **Install app**. On iPhone Safari, use **Share → Add to Home Screen**.

## Updating cached static assets

When changing cached resources, increment `CACHE_VERSION` in `static/pwa/service-worker.js`. The new worker removes previous Salon De Nature PWA caches during activation.
