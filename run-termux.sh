#!/data/data/com.termux/files/usr/bin/bash
# IELTS Controller'ni Termux'da doimiy ishlatish:
#  - termux-wake-lock: telefon uxlaganda ham Android Termux'ni to‘xtatmasin;
#  - bot xato bilan to‘xtasa — 10 soniyadan keyin avtomatik qayta ishga tushadi;
#  - log: bot.log (oxirgi ~5 MB saqlanadi).
# Ishlatish:  ./run-termux.sh        (to‘xtatish: Ctrl+C)
cd "$(dirname "$0")"

if [ ! -f .env ]; then
    echo "Avval sozlang:  python main.py"
    exit 1
fi

command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

trap 'echo; echo "To‘xtatildi."; command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock; exit 0' INT TERM

while true; do
    if [ -f bot.log ] && [ "$(wc -c < bot.log)" -gt 5242880 ]; then
        tail -c 1048576 bot.log > bot.log.tmp && mv bot.log.tmp bot.log
    fi
    echo "[$(date '+%F %T')] Bot ishga tushdi" | tee -a bot.log
    python main.py < /dev/null 2>&1 | tee -a bot.log
    code=${PIPESTATUS[0]}
    if [ "$code" -eq 0 ]; then
        echo "Bot to‘xtadi (kod 0)."
        break
    fi
    if tail -n 5 bot.log | grep -q "BOT_TOKEN noto"; then
        echo "Token noto‘g‘ri — qayta ishga tushirilmaydi. Tuzatish: python main.py --setup"
        break
    fi
    echo "[$(date '+%F %T')] Bot to‘xtadi (kod $code). 10 soniyadan keyin qayta ishga tushadi..." | tee -a bot.log
    sleep 10
done
