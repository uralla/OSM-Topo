# WordPress map status block

`garmin-map-status.php` is the small WordPress plugin used on the public Garmin map page.

It provides the shortcode:

```text
[garmin_map_status]
```

The shortcode reads the public build-status feed:

```text
https://www.uralla.ru/garmin.img/map-update-status.json
```

and renders the map catalog with current build state, publication/update times, IMG and BaseCamp download buttons, artifact sizes, and the `recipe_state` warning for maps built by an older map recipe.

## Installation

1. Copy `garmin-map-status.php` to a WordPress plugin directory, for example:

   ```text
   wp-content/plugins/garmin-map-status/garmin-map-status.php
   ```

2. Activate the plugin in WordPress.
3. Insert `[garmin_map_status]` into the Garmin map page.

The plugin does not require external JavaScript, icon libraries, or third-party CSS. The JSON response is cached in WordPress for 60 seconds to avoid requesting the status file for every page view.

## Status compatibility

The block understands the public states `current`, `due`, `building`, `error`, `interrupted`, and `unknown`.

When `recipe_state` is present, `stale` and `legacy` maps are marked with `⚠️`. The map remains downloadable; the warning only means that it was built with a previous version of the style/build algorithms and will become fully current after the next successful rebuild.

If `recipe_state` is absent (for example while an older status generator is still running), the page still renders normally and simply omits the recipe warning.

## Maintenance

The repository copy is the canonical source for the site plugin. If the live WordPress code is changed, mirror the tested change back to `web/wordpress/garmin-map-status.php` so the deployed site and repository do not drift apart.
