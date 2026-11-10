#!/data/data/com.termux/files/usr/bin/bash
# IELTS Controller — Termux (Android) uchun o‘rnatish.
# Ishlatish:  bash install-termux.sh
set -e
cd "$(dirname "$0")"

TUR_INDEX="https://termux-user-repository.github.io/pypi/"

echo "==> 1/4 Termux paketlari yangilanmoqda..."
pkg update -y

echo "==> 2/4 Python va tayyor paketlar (Pillow, kompilyator)..."
pkg install -y python python-pillow build-essential

echo "==> 3/4 Grafik uchun matplotlib (ixtiyoriy)..."
if pkg install -y matplotlib; then
    echo "    matplotlib o‘rnatildi — grafiklar ishlaydi."
else
    echo "    ! matplotlib o‘rnatilmadi. Bot ishlayveradi, faqat grafiklar chiqmaydi."
fi

echo "==> 4/4 Python kutubxonalari (pip)..."
if ! python -m pip install --extra-index-url "$TUR_INDEX" -r requirements-termux.txt; then
    echo
    echo "! pip o‘rnatishda xato. Ko‘pincha sabab — pydantic-core uchun tayyor wheel topilmadi."
    echo "  Rust bilan qayta urinib ko‘ring (10-20 daqiqa kompilyatsiya qilinadi):"
    echo "      pkg install -y rust"
    echo "      python -m pip install --extra-index-url $TUR_INDEX -r requirements-termux.txt"
    exit 1
fi

chmod +x run-termux.sh 2>/dev/null || true

# Telefon qayta yonganda avtomatik ishga tushirish (Termux:Boot ilovasi o‘rnatilgan bo‘lsa ishlaydi)
BOOT_DIR="$HOME/.termux/boot"
mkdir -p "$BOOT_DIR"
cat > "$BOOT_DIR/ielts-controller.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
cd "$(pwd)" && ./run-termux.sh > /dev/null 2>&1
EOF
chmod +x "$BOOT_DIR/ielts-controller.sh"
echo "    Avto-start fayli: $BOOT_DIR/ielts-controller.sh (Termux:Boot ilovasi kerak)"

echo
echo "Tayyor! Endi birinchi marta ishga tushiring (sozlash savollari beriladi):"
echo "    python main.py"
echo "Sozlab bo‘lgach, fonda doimiy ishlatish uchun:"
echo "    ./run-termux.sh"
