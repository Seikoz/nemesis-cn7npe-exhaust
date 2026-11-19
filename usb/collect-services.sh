#!/system/bin/sh
case "$0" in
    */*) SERVICE_USB=${0%/*} ;;
    *) SERVICE_USB=. ;;
esac
exec /system/bin/sh "$SERVICE_USB/collect.sh" --services-only
