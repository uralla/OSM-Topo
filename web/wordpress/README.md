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

and renders the map catalog with current build state, publication/update times, Garmin IMG and BaseCamp download buttons and artifact sizes.

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

The IMG button uses the URL provided by the status feed and displays “Скачать IMG
(ZIP)” for an archived map. The BaseCamp button is hidden for all maps when
the feed has `mapsource_enabled: false`. Older feeds without the field retain
the BaseCamp buttons.

## Maintenance

The repository copy is the canonical source for the site plugin. If the live WordPress code is changed, mirror the tested change back to `web/wordpress/garmin-map-status.php` so the deployed site and repository do not drift apart.
