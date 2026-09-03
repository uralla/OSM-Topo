# Build daemon

`uralla_build.daemon` continuously uses the normal manifest/history/build pipeline to publish due Garmin products without a separate scheduling database.

## Scheduling behavior

- queue order comes from `config/maps.yaml`: lower `priority` first, then never-built products, then overdue age;
- only products whose update interval is due are started;
- one product pipeline runs at a time; the existing global `pipeline.lock` remains authoritative;
- the manifest is reloaded before every scheduling decision, so priority/enabled/interval changes do not require a daemon restart;
- after a failed product build, that product receives an in-memory 15 minute backoff by default so another due product can run instead of entering a tight failure loop;
- only a successfully published pipeline updates successful-build history.

## Public update status

The daemon atomically maintains `map-update-status.txt` in the configured publication root (`output` in the normal workspace). The file is UTF-8 text intended to sit beside the published maps.

Each enabled product shows its last successful publication, approximate next due time, remaining/overdue time and current state (`актуальна`, `ожидает обновления`, `собирается`, `ошибка`, `прервано`). The timestamp header is explicitly UTC and the file explains that future dates are approximate.

The table does not have its own scheduler. It is rendered from the same manifest, successful-build history, update intervals and deterministic queue used by the daemon. Failed or interrupted builds may change the displayed state but never move the last-success timestamp or the next-update TTL basis.

The file is replaced through a temporary file plus atomic rename, so readers never see a partially written table. It is refreshed during normal daemon scheduling, when a daemon-started build becomes running, and after that build terminates.

## Crash and stop behavior

The daemon owns `state/daemon.lock`, so a second daemon instance exits instead of creating a competing scheduler.

On `SIGTERM`/`SIGINT` the daemon sends `SIGINT` to the active `build-product` process. `PipelineRunner` then marks the build `interrupted` and `StageRunner` terminates the current external stage process group.

If the machine or process is killed without graceful cleanup, a `running` build may remain in SQLite. The daemon repairs such stale records to `interrupted` whenever `pipeline.lock` is free. It never performs that repair while a real product pipeline owns the lock.

## Manual validation

After `setup.sh`, use the generated workspace launcher. With the default workspace:

```bash
cd ~/garmin_lab
./start queue
./start daemon --once
```

`--once` builds at most one currently due product and exits. It is useful before enabling systemd. Note that it is not a dry run: if a product is due, a real build and publication are performed.

Foreground continuous mode:

```bash
cd ~/garmin_lab
./start daemon
```

Stop it with `Ctrl+C` and confirm that an active build becomes `interrupted`, not permanently `running`.

Optional timing overrides:

```bash
./start daemon --idle-seconds 300 --failure-retry-seconds 900
```

## systemd installation on Linux

Run the installer as the same normal Unix user that owns the Garmin workspace. Do not invoke the script itself with `sudo`; it asks for sudo only when writing/enabling the system service.

Default `~/garmin_lab` workspace:

```bash
bash scripts/install-daemon-service.sh
```

Custom workspace:

```bash
bash scripts/install-daemon-service.sh /path/to/garmin_lab
```

The service runs the generated `workspace/start daemon` launcher, so it automatically uses the same virtualenv, repository checkout and machine-local `host.yaml` created by `setup.sh`.

Useful commands:

```bash
systemctl status uralla-build-daemon.service
journalctl -u uralla-build-daemon.service -f
sudo systemctl restart uralla-build-daemon.service
sudo systemctl stop uralla-build-daemon.service
```

The unit uses `Restart=on-failure` and `KillMode=mixed`: normal service stop first gives the daemon time to interrupt the current build cleanly; only after the stop timeout may systemd kill the remaining process group.
