#!/bin/sh
# (Re)load the WHS dataset into TDB2, then start Fuseki with the read-only config.
set -e
DB=/fuseki/databases/whs
rm -rf "$DB"
/jena-fuseki/tdbloader2 --loc "$DB" /staging/whs-all.trig 2>/dev/null \
  || /jena/bin/tdb2.tdbloader --loc "$DB" /staging/whs-all.trig
exec /jena-fuseki/fuseki-server --config=/fuseki/configuration/whs.ttl
