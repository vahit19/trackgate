#!/usr/bin/env bash
# Deploys TrackGate to vahitferyad.com/trackgate/: the page into the site's web root and the analyst API
# as one small container on 127.0.0.1:8095. Touches nothing else on the shared server: backs up the
# web root and the site's nginx file, checks every site before and after, reloads (never restarts) nginx.
# Usage (from the repo root):  bash deploy/deploy_trackgate.sh
set -euo pipefail
HOST=${HOST:-root@116.203.228.141}
KEY=${KEY:-$HOME/.ssh/id_ed25519_nader}
ENVFILE=${ENVFILE:-../vf-support-agent/.env}
SSH=(ssh -i "$KEY" -o IdentitiesOnly=yes -o BatchMode=yes "$HOST")
SCP=(scp -i "$KEY" -o IdentitiesOnly=yes -o BatchMode=yes)
cd "$(dirname "$0")/.."

OR_KEY=$(grep -h '^OPENROUTER_API_KEY=' "$ENVFILE" | head -1 | cut -d= -f2- | tr -d '"\r')
[ -n "$OR_KEY" ] || { echo "OPENROUTER_API_KEY not found in $ENVFILE"; exit 1; }
[ -s deploy/site/index.html ] || { echo "run scripts/build_panel.py first"; exit 1; }

echo "== 1/5 backup"
"${SSH[@]}" 'set -e; TS=$(date +%Y%m%d-%H%M%S); mkdir -p /root/backups
  tar czf /root/backups/vahitferyad.com-$TS.tgz -C /var/www vahitferyad.com
  cp /etc/nginx/sites-available/vahitferyad.com /root/backups/nginx-vahitferyad.com-$TS
  echo "backup $TS"'

echo "== 2/5 API container"
"${SSH[@]}" 'mkdir -p /opt/trackgate/data && chown 10001 /opt/trackgate/data'
printf 'OPENROUTER_API_KEY=%s\nTRACKGATE_MODEL=anthropic/claude-haiku-5.5\nTRACKGATE_DAILY_CALLS=1500\n' "$OR_KEY" \
  | "${SSH[@]}" 'umask 077; cat > /opt/trackgate/.env'
"${SCP[@]}" deploy/Dockerfile deploy/trackgate_api.py "$HOST":/opt/trackgate/
"${SSH[@]}" 'set -e; cd /opt/trackgate
  docker build -q -t trackgate-api . >/dev/null
  docker rm -f trackgate-api >/dev/null 2>&1 || true
  docker run -d --name trackgate-api --restart unless-stopped -m 128m --cpus 0.5 --pids-limit 64 \
    -p 127.0.0.1:8095:8095 --env-file /opt/trackgate/.env -v /opt/trackgate/data:/data trackgate-api >/dev/null
  sleep 2; curl -fsS 127.0.0.1:8095/trackgate/api/health; echo'

echo "== 3/5 page"
"${SSH[@]}" 'mkdir -p /var/www/vahitferyad.com/trackgate'
"${SCP[@]}" deploy/site/index.html deploy/site/trackgate-tour.mp4 deploy/site/trackgate-tour.jpg "$HOST":/var/www/vahitferyad.com/trackgate/
"${SSH[@]}" 'chmod 644 /var/www/vahitferyad.com/trackgate/*'

echo "== 4/5 nginx (only the vahitferyad.com file)"
"${SSH[@]}" 'set -e
  SITES="vahitferyad.com pubscope.org analytics.pubscope.org codeg.pubscope.org resolutionproof.pro nadiribrahimoglu.com cemaltinel.info gonulluyuzbiz.xyz nl2t.xyz"
  check() { for s in $SITES; do printf "%s:%s " "$s" "$(curl -sk -o /dev/null -w "%{http_code}" --max-time 10 --resolve $s:443:127.0.0.1 https://$s/)"; done; echo; }
  BEFORE=$(check); echo "before: $BEFORE"
  F=/etc/nginx/sites-available/vahitferyad.com
  if ! grep -q "trackgate/api" $F; then
    python3 - "$F" <<"PY"
import sys
p = sys.argv[1]; s = open(p).read()
block = """    # TrackGate analyst API (container trackgate-api, 127.0.0.1:8095)
    location = /trackgate { return 301 /trackgate/; }
    location ^~ /trackgate/api/ {
        limit_req zone=perip burst=40 nodelay;
        client_max_body_size 256k;
        proxy_pass http://127.0.0.1:8095;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 90s;
    }
"""
anchor = "    location / {"
assert s.count(anchor) == 1, "anchor not unique"
open(p, "w").write(s.replace(anchor, block + anchor))
PY
  fi
  if nginx -t 2>/dev/null; then systemctl reload nginx; else
    echo "nginx -t failed, restoring"; cp "$(ls -t /root/backups/nginx-vahitferyad.com-* | head -1)" $F; nginx -t; exit 1; fi
  sleep 1; AFTER=$(check); echo "after:  $AFTER"
  [ "$BEFORE" = "$AFTER" ] || echo "WARNING: a site changed status, compare the two lines above"'

echo "== 5/5 live check"
curl -fsS -o /dev/null -w "page %{http_code}\n" https://vahitferyad.com/trackgate/
curl -fsS https://vahitferyad.com/trackgate/api/health; echo
echo "done: https://vahitferyad.com/trackgate/"
