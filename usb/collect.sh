#!/system/bin/sh
# One shot; reads selected stock files, writes only beside this script on USB.
export PATH=/sbin:/vendor/bin:/system/sbin:/system/bin:/system/xbin
export LD_LIBRARY_PATH=/vendor/lib:/system/lib
umask 077

case "$0" in
    */*) USB_DIR=${0%/*} ;;
    *) USB_DIR=. ;;
esac
USB_DIR=$(cd "$USB_DIR" && pwd -P) || exit 1
case "$USB_DIR" in
    /storage/usb[0-9]|/mnt/media_rw/usb[0-9]) ;;
    *) echo "Run from a NEMESIS USB drive, not internal storage."; exit 1 ;;
esac
[ -f "$USB_DIR/CN7NPE-EXHAUST-RESEARCH.txt" ] || exit 1

PRODUCT=$(getprop ro.build.product) || exit 1
case "$PRODUCT" in
    CN7NPE.KOR.0000.V039.001.260902|CN7NPE.KOR.S5W_M.V039.001.260902) ;;
    *) echo "Requires CN7NPE KOR V039.001.260902. Nothing collected."; exit 2 ;;
esac
[ "$(getprop ro.board.platform)" = tcc803x ] || {
    echo "Requires the TCC803x head unit. Nothing collected."
    exit 2
}

# mkdir is exclusive. Never overwrite a previous export or follow its symlink.
INDEX=1
OUT=
while [ "$INDEX" -le 20 ]; do
    CANDIDATE="$USB_DIR/CN7NPE-exhaust-private-$INDEX"
    if mkdir "$CANDIDATE" 2>/dev/null; then
        OUT=$CANDIDATE
        break
    fi
    INDEX=$((INDEX + 1))
done
[ -n "$OUT" ] || { echo "Cannot create output directory on USB."; exit 3; }
mkdir "$OUT/stock" || exit 3

REPORT="$OUT/report.txt"
ERRORS=0
FRAMEWORK=0
NMODE=0
{
    echo "CN7NPE exhaust research collector 0.1.0"
    echo "flap_control=NOT_IMPLEMENTED"
    echo "product=$PRODUCT"
    echo "platform=tcc803x"
    echo "android=$(getprop ro.build.version.release)"
    echo "sdk=$(getprop ro.build.version.sdk)"
    echo "Stock files below are private analysis inputs, not redistributable assets."
} > "$REPORT" || exit 3

copy_stock() {
    SOURCE=$1
    DEST=$2
    [ -f "$SOURCE" ] && [ -r "$SOURCE" ] || return 1
    if cp "$SOURCE" "$OUT/stock/$DEST"; then
        echo "copied=$SOURCE -> stock/$DEST" >> "$REPORT" || exit 3
        return 0
    fi
    echo "copy_failed=$SOURCE" >> "$REPORT" || exit 3
    ERRORS=$((ERRORS + 1))
    return 1
}

# Paired JAR/ODEX and boot dependencies for off-car analysis. No /data, modem,
# logcat, contact database, VIN, settings database or full getprop collection.
for STEM in automotive framework framework2 services core ext android.policy; do
    for EXT in jar odex; do
        SOURCE="/system/framework/$STEM.$EXT"
        if copy_stock "$SOURCE" "$STEM.$EXT"; then
            [ "$STEM" = automotive ] && FRAMEWORK=$((FRAMEWORK + 1))
        fi
    done
done

# Enumerate only system packages; keep only N-mode package identifiers.
# Paths from PackageManager are data, never evaluated as shell code.
if pm list packages -s > "$OUT/system-packages.tmp" 2>/dev/null; then
    while IFS= read -r LINE; do
        PKG=${LINE#package:}
        case "$PKG" in
            com.hkmc.*nmode*|com.mobis.*nmode*)
                case "$PKG" in *[!a-zA-Z0-9._]*) continue ;; esac
                echo "$PKG" >> "$OUT/nmode-packages.txt" || exit 3
                ;;
        esac
    done < "$OUT/system-packages.tmp"
else
    echo "package_list_failed=yes" >> "$REPORT"
    ERRORS=$((ERRORS + 1))
fi

if [ -f "$OUT/nmode-packages.txt" ]; then
    APP_INDEX=0
    while IFS= read -r PKG; do
        echo "nmode_package=$PKG" >> "$REPORT"
        if ! pm path "$PKG" > "$OUT/package-paths.tmp" 2>/dev/null; then
            ERRORS=$((ERRORS + 1))
            continue
        fi
        while IFS= read -r LINE; do
            case "$LINE" in package:/system/*.apk) ;;
                *) continue ;;
            esac
            SOURCE=${LINE#package:}
            case "$SOURCE" in */../*|*/./*) continue ;; esac
            if copy_stock "$SOURCE" "nmode-$APP_INDEX.apk"; then
                NMODE=$((NMODE + 1))
                copy_stock "${SOURCE%.apk}.odex" "nmode-$APP_INDEX.odex"
            fi
            APP_INDEX=$((APP_INDEX + 1))
        done < "$OUT/package-paths.tmp"
    done < "$OUT/nmode-packages.txt"
fi

# rm only our two temporary, newly created files; no recursive deletion.
rm -f "$OUT/system-packages.tmp" "$OUT/package-paths.tmp"
{
    echo "automotive_files=$FRAMEWORK"
    echo "nmode_apks=$NMODE"
    echo "copy_or_package_errors=$ERRORS"
    if [ "$FRAMEWORK" -gt 0 ] && [ "$NMODE" -gt 0 ] && [ "$ERRORS" -eq 0 ]; then
        echo "collection=COMPLETE"
    else
        echo "collection=INCOMPLETE"
    fi
} >> "$REPORT" || exit 3

cat > "$OUT/PRIVATE-README.txt" <<'PRIVATE'
배기 플랩 제어 기능은 아직 없습니다. 분석용 추출 파일입니다.
이 폴더를 PC에서 ZIP으로 압축해 개발 대화에 비공개로 첨부해 주세요.
stock/에는 제조사 APK/JAR/ODEX가 들어 있습니다.
공개 GitHub 저장소, 릴리스, 이슈에 올리지 마세요.
report.txt의 collection=COMPLETE는 추출 완료일 뿐 제어 성공이 아닙니다.
시스템 파일을 수정하거나 배기 플랩 명령을 보내지 않았습니다.
PRIVATE
[ "$?" -eq 0 ] || exit 3
sync
echo "Saved: $OUT"
if [ "$FRAMEWORK" -eq 0 ] || [ "$NMODE" -eq 0 ] || [ "$ERRORS" -ne 0 ]; then
    echo "Some required inputs are missing. Keep the partial export for analysis."
    exit 4
fi
echo "Collection complete. Exhaust flap control is not implemented."
exit 0
