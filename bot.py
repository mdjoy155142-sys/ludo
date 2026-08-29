import os
from flask import Flask, request, jsonify, render_template_string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8713892015:AAFnziA_o3Q5o61dqrWwBjhd6TB5Glzz0E4"
WEBAPP_URL = "https://telegram-bot-oh28.onrender.com"

app = Flask(__name__)
user_balances = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <title>প্রো আর্নিং গেম জোন - প্রিমিয়াম এডিশন</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { background: #0b0f19; color: white; text-align: center; font-family: sans-serif; padding: 10px; margin: 0; }
        .box { background: #1e293b; padding: 12px; border-radius: 15px; margin-bottom: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        .btn { background: #22c55e; color: white; padding: 12px; width: 100%; border: none; border-radius: 10px; cursor: pointer; font-size: 15px; font-weight: bold; }
        .btn:active { transform: scale(0.98); }
        .stop-btn { background: #ef4444 !important; }
        input, select { width: 90%; padding: 10px; margin: 5px; border-radius: 5px; border: none; background: #0f172a; color: white; text-align: center; font-size: 15px; outline: none; }
        .game-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 10px; }
        .game-card { background: #334155; padding: 12px; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 13px; text-align: center; }
        .back-btn { background: #475569; margin-bottom: 8px; padding: 6px 12px; border: none; border-radius: 6px; color: white; cursor: pointer; float: left; font-size: 12px; }
        .game-section { display: none; }
        .active-section { display: block; }
        canvas { background: #0b0f19; border-radius: 10px; margin: 5px auto; display: block; }
        .slot-machine-box { background: linear-gradient(135deg, #450a0a, #1e1b4b); border: 2px solid #ef4444; border-radius: 12px; padding: 10px; margin: 10px auto; max-width: 350px; }
        .history-bar { display: flex; gap: 5px; justify-content: center; overflow-x: auto; margin-bottom: 8px; padding: 4px; }
        .history-tag { background: #334155; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; color: #38bdf8; }
    </style>
</head>
<body>
    <div class="box">
        <h4>💰 মূল ব্যালেন্স: <span id="balanceText">0.00</span> টাকা</h4>
    </div>

    <div id="gameLobby" class="game-section active-section box">
        <h3>🎮 প্রো গেম জোন</h3>
        <div class="game-grid">
            <div class="game-card" onclick="openGame('rocketGame')">🚀 রকেট ক্র্যাশ</div>
            <div class="game-card" onclick="openGame('slotsGame')">🎰 স্লট মেশিন</div>
            <div class="game-card" onclick="openGame('boxingGame')">🥊 বক্সিং কিং</div>
            <div class="game-card" onclick="openGame('spinGame')">🎡 লাকি স্পিন</div>
        </div>
    </div>

    <div id="rocketGame" class="game-section box">
        <button class="back-btn" onclick="closeGame()">⬅ ব্যাক</button>
        <h3 style="margin:0;">🚀 রকেট ক্র্যাশ</h3>
        <div class="history-bar" id="rocketHistory"></div>
        <canvas id="rocketCanvas" width="350" height="180"></canvas>
        <input type="number" id="rocketBet" value="50" min="1">
        <input type="number" id="autoCashInput" placeholder="অটো ক্যাশ-আউট (যেমন: 2.00)" step="0.1" min="1.1">
        <p id="rocketStatus" style="color: #94a3b8; font-size: 12px; margin: 5px;">বেট প্লেস করুন</p>
        <button class="btn" id="rocketBtn" onclick="toggleRocketGame()">বেট নিশ্চিত করুন</button>
    </div>

    <div id="slotsGame" class="game-section box">
        <button class="back-btn" onclick="closeGame()">⬅ ব্যাক</button>
        <h3 style="margin:0;">🎰 স্লট মেশিন (৩×৩)</h3>
        <canvas id="slotsCanvas" width="350" height="210"></canvas>
        <input type="number" id="slotsBet" value="50" min="1">
        <p id="slotsStatus" style="color: #94a3b8; font-size: 12px; margin: 5px;">স্লট স্পিন করুন</p>
        <button class="btn" id="slotsBtn" onclick="playSlotsGame()">স্লট ঘোড়ান</button>
    </div>

    <div id="boxingGame" class="game-section box">
        <button class="back-btn" onclick="closeGame()">⬅ ব্যাক</button>
        <h3 style="margin:0; color: #f59e0b;">🥊 বক্সিং কিং</h3>
        <div class="slot-machine-box"><canvas id="boxingCanvas" width="330" height="150" style="background:#000; border-radius:8px; margin:0 auto;"></canvas></div>
        <input type="number" id="boxingBet" value="50" min="1">
        <p id="boxingStatus" style="color: #94a3b8; font-size: 12px; margin: 5px;">স্পিন করতে প্রস্তুত</p>
        <button class="btn" onclick="playBoxingGame()" style="background: #ef4444; color: #fff;">🥊 বক্সিং স্পিন করুন</button>
    </div>

    <div id="spinGame" class="game-section box">
        <button class="back-btn" onclick="closeGame()">⬅ ব্যাক</button>
        <h3 style="margin:0; color: #38bdf8;">🎡 লাকি স্পিন হুইল</h3>
        <canvas id="realWheelCanvas" width="220" height="220"></canvas>
        <input type="number" id="spinBet" value="50" min="1">
        <p id="spinStatus" style="color: #94a3b8; font-size: 12px; margin: 5px;">স্পিন করতে বেট দিন</p>
        <button class="btn" id="spinBtn" onclick="playRealWheel()">চাকা ঘোরান</button>
    </div>

    <div class="box">
        <h3>📤 টাকা উত্তোলন</h3>
        <input type="text" id="witPhone" placeholder="বিকাশ নম্বর">
        <input type="number" id="witAmount" placeholder="পরিমাণ (১২০০+)" min="1">
        <button class="btn stop-btn" style="margin-top: 5px;" onclick="submitWithdraw()">উত্তোলন রিকোয়েস্ট</button>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        const urlParams = new URLSearchParams(window.location.search);
        let userId = urlParams.get('user_id') || (tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : "123456789");
        let balance = 0.0;

        async function fetchBalance() {
            try {
                let res = await fetch(`/get_balance/${userId}`);
                let data = await res.json();
                if (data.status === "success") { balance = data.balance; document.getElementById("balanceText").innerText = balance.toFixed(2); }
            } catch (err) { console.error(err); }
        }

        async function updateBalanceInBackend(diff) {
            try {
                let res = await fetch('/update_balance', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId, amount_diff: diff })
                });
                let data = await res.json();
                if (data.status === "success") { balance = data.new_balance; document.getElementById("balanceText").innerText = balance.toFixed(2); }
            } catch (err) { console.error(err); }
        }
        fetchBalance();

        function openGame(gameId) {
            document.querySelectorAll('.game-section').forEach(s => s.classList.remove('active-section'));
            document.getElementById(gameId).classList.add('active-section');
            if (gameId === 'rocketGame') { if (!isRocketRunning) startRocketLoop(); } else { isRocketRunning = false; }
            if (gameId === 'slotsGame') drawSlotsGrid([['🍒', '🍋', '🔔'],['⭐', '💎', '🍉'],['🔔', '🍒', '🍋']], "স্লট স্পিন করুন");
            else if (gameId === 'boxingGame') drawBoxing(['🥊', '🥋', '🏆'], "বক্সিং স্পিন করুন");
            else if (gameId === 'spinGame') drawWheel(0);
        }

        function closeGame() {
            document.querySelectorAll('.game-section').forEach(s => s.classList.remove('active-section'));
            document.getElementById('gameLobby').classList.add('active-section');
        }

        const rocketCanvas = document.getElementById('rocketCanvas');
        const rctx = rocketCanvas.getContext('2d');
        let rocketState = "WAITING", multiplier = 1.00, crashAt = 1.00, rocketBetVal = 0, hasRocketBet = false, isRocketRunning = false, rx = 20, ry = 150;
        let rocketHistory = [];

        function startRocketLoop() {
            isRocketRunning = true; rocketState = "WAITING"; multiplier = 1.00; hasRocketBet = false; rx = 20; ry = 150;
            let countdown = 7; 
            let timer = setInterval(() => {
                if (!isRocketRunning) { clearInterval(timer); return; }
                if (document.getElementById('rocketGame').classList.contains('active-section')) { drawRocketScene("ফ্লাইট শুরু: " + countdown + "s", "#38bdf8"); }
                countdown--;
                if (countdown < 0) { clearInterval(timer); launchRealRocket(); }
            }, 1000);
        }

        function launchRealRocket() {
            if (!isRocketRunning) return;
            rocketState = "FLYING";
            crashAt = parseFloat((Math.random() * 3 + 1.2).toFixed(2));
            if (hasRocketBet) { document.getElementById("rocketBtn").innerText = "💰 ক্যাশ আউট"; document.getElementById("rocketBtn").className = "btn stop-btn"; }
            
            let flyInterval = setInterval(async () => {
                if (!isRocketRunning || rocketState !== "FLYING") { clearInterval(flyInterval); return; }
                multiplier += 0.03;
                if (rx < 250) rx += 1.2; if (ry > 40) ry -= 0.9;
                
                let autoCashVal = parseFloat(document.getElementById("autoCashInput").value);
                if (hasRocketBet && !isNaN(autoCashVal) && multiplier >= autoCashVal && autoCashVal < crashAt) { await cashOutRocket(autoCashVal); }
                if (document.getElementById('rocketGame').classList.contains('active-section')) { drawRocketScene(multiplier.toFixed(2) + "x", "#22c55e"); }
                
                if (multiplier >= crashAt) {
                    clearInterval(flyInterval);
                    rocketState = "CRASHED";
                    rocketHistory.unshift(crashAt.toFixed(2) + "x"); if(rocketHistory.length > 5) rocketHistory.pop();
                    document.getElementById("rocketHistory").innerHTML = rocketHistory.map(h => `<span class="history-tag">${h}</span>`).join('');
                    if (document.getElementById('rocketGame').classList.contains('active-section')) { drawRocketScene("💥 ক্র্যাশ " + crashAt + "x", "#ef4444"); }
                    if(hasRocketBet) { hasRocketBet = false; document.getElementById("rocketStatus").innerText = "💥 ক্র্যাশ! হেরে গেছেন।"; }
                    document.getElementById("rocketBtn").innerText = "বেট নিশ্চিত করুন"; document.getElementById("rocketBtn").className = "btn";
                    setTimeout(startRocketLoop, 3000);
                }
            }, 60);
        }

        function drawRocketScene(text, color) {
            rctx.clearRect(0, 0, rocketCanvas.width, rocketCanvas.height);
            rctx.strokeStyle = '#1e293b'; rctx.lineWidth = 1; rctx.beginPath(); rctx.moveTo(0, 150); rctx.lineTo(350, 150); rctx.stroke();
            if (rocketState === "FLYING") { rctx.strokeStyle = '#22c55e'; rctx.lineWidth = 3; rctx.beginPath(); rctx.moveTo(20, 150); rctx.lineTo(rx, ry); rctx.stroke(); }
            rctx.font = "24px sans-serif"; rctx.fillText(rocketState === "CRASHED" ? "💥" : "🚀", rx, ry);
            rctx.fillStyle = color; rctx.font = "bold 22px sans-serif"; rctx.textAlign = "center"; rctx.fillText(text, rocketCanvas.width / 2, 40);
        }

        async function cashOutRocket(mult) {
            hasRocketBet = false; let win = rocketBetVal * mult;
            await updateBalanceInBackend(win);
            document.getElementById("rocketStatus").innerText = `🎉 জিতেছেন ${win.toFixed(2)} টাকা (${mult}x)`;
            let btn = document.getElementById("rocketBtn"); btn.innerText = "বেট নিশ্চিত করুন"; btn.className = "btn";
        }

        async function toggleRocketGame() {
            let betInput = document.getElementById("rocketBet"); let btn = document.getElementById("rocketBtn");
            if (rocketState === "WAITING") {
                if (hasRocketBet) return;
                rocketBetVal = parseFloat(betInput.value);
                if (isNaN(rocketBetVal) || rocketBetVal <= 0 || rocketBetVal > balance) { alert("সঠিক বেট বা ব্যালেন্স নেই!"); return; }
                await updateBalanceInBackend(-rocketBetVal);
                hasRocketBet = true; btn.innerText = "✅ বেট প্লেসড";
            } else if (rocketState === "FLYING" && hasRocketBet) { await cashOutRocket(multiplier); }
        }

        const slotsCanvas = document.getElementById('slotsCanvas');
        const slotCtx = slotsCanvas.getContext('2d');
        function drawSlotsGrid(gridData, text) {
            slotCtx.clearRect(0, 0, slotsCanvas.width, slotsCanvas.height);
            let icons = gridData, cellWidth = 85, cellHeight = 50, startX = 45, startY = 10;
            slotCtx.font = "26px sans-serif"; slotCtx.textAlign = "center"; slotCtx.textBaseline = "middle";
            for (let r = 0; r < 3; r++) {
                for (let c = 0; c < 3; c++) {
                    let bx = startX + c * (cellWidth + 10), by = startY + r * (cellHeight + 8);
                    slotCtx.fillStyle = '#0f172a'; slotCtx.fillRect(bx, by, cellWidth, cellHeight);
                    slotCtx.strokeStyle = '#38bdf8'; slotCtx.strokeRect(bx, by, cellWidth, cellHeight);
                    slotCtx.fillText(icons[r][c], bx + cellWidth / 2, by + cellHeight / 2);
                }
            }
            slotCtx.fillStyle = "#38bdf8"; slotCtx.font = "bold 13px sans-serif"; slotCtx.fillText(text, slotsCanvas.width / 2, 185);
        }

        async function playSlotsGame() {
            let bet = parseFloat(document.getElementById('slotsBet').value);
            if (isNaN(bet) || bet <= 0 || bet > balance) { alert("পর্যাপ্ত ব্যালেন্স নেই!"); return; }
            await updateBalanceInBackend(-bet);
            let icons = ['🍒', '🍋', '🔔', '⭐', '💎', '🍉'], count = 0;
            let interval = setInterval(async () => {
                count++;
                drawSlotsGrid(Array.from({length:3}, ()=>Array.from({length:3}, ()=>icons[Math.floor(Math.random()*icons.length)])), "রোল হচ্ছে...");
                if (count > 10) {
                    clearInterval(interval);
                    let win = Math.random() < 0.3;
                    let finalGrid = Array.from({length:3}, ()=>Array.from({length:3}, ()=>icons[Math.floor(Math.random()*icons.length)]));
                    if (win) {
                        let prize = bet * 2; await updateBalanceInBackend(prize);
                        drawSlotsGrid(finalGrid, `🎉 ২ গুণ জিতেছেন! (${prize} টাকা)`);
                    } else { drawSlotsGrid(finalGrid, "❌ হেরে গেছেন!"); }
                }
            }, 60);
        }

        const boxingCanvas = document.getElementById('boxingCanvas');
        const bCtx = boxingCanvas.getContext('2d');
        function drawBoxing(symbols, text) {
            bCtx.clearRect(0, 0, boxingCanvas.width, boxingCanvas.height);
            bCtx.fillStyle = '#0f172a'; bCtx.fillRect(40, 30, 250, 70);
            bCtx.font = "30px sans-serif"; bCtx.textAlign = "center";
            bCtx.fillText(symbols[0], 90, 75); bCtx.fillText(symbols[1], 165, 75); bCtx.fillText(symbols[2], 240, 75);
            bCtx.fillStyle = "#f59e0b"; bCtx.font = "bold 13px sans-serif"; bCtx.fillText(text, boxingCanvas.width / 2, 130);
        }
        async function playBoxingGame() {
            let bet = parseFloat(document.getElementById('boxingBet').value);
            if (isNaN(bet) || bet <= 0 || bet > balance) { alert("ব্যালেন্স কম আছে!"); return; }
            await updateBalanceInBackend(-bet);
            let icons = ['🥊', '🥋', '🏆', '⭐', '👑'], count = 0;
            let interval = setInterval(async () => {
                count++;
                drawBoxing([icons[Math.floor(Math.random()*5)], icons[Math.floor(Math.random()*5)], icons[Math.floor(Math.random()*5)]], "ফাইট চলছে...");
                if (count > 10) {
                    clearInterval(interval);
                    if (Math.random() < 0.25) {
                        let prize = bet * 3; await updateBalanceInBackend(prize);
                        drawBoxing(['👑', '👑', '👑'], `🎉 নকআউট জয়! (${prize} টাকা)`);
                    } else { drawBoxing(['🥊', '🥋', '⭐'], "❌ হেরে গেছেন!"); }
                }
            }, 60);
        }

        const wheelCanvas = document.getElementById('realWheelCanvas');
        const wCtx = wheelCanvas.getContext('2d');
        const slices = [{text:"2x", color:"#22c55e"}, {text:"0x", color:"#ef4444"}, {text:"3x", color:"#38bdf8"}, {text:"0x", color:"#ef4444"}, {text:"1.5x", color:"#f59e0b"}, {text:"0x", color:"#ef4444"}];
        
        function drawWheel(angle) {
            let width = wheelCanvas.width, height = wheelCanvas.height, center = width / 2, radius = center - 15;
            wCtx.clearRect(0, 0, width, height); wCtx.save(); wCtx.translate(center, center); wCtx.rotate(angle);
            let arc = (2 * Math.PI) / slices.length;
            for (let i = 0; i < slices.length; i++) {
                wCtx.beginPath(); wCtx.fillStyle = slices[i].color; wCtx.moveTo(0, 0); wCtx.arc(0, 0, radius, i * arc, (i + 1) * arc); wCtx.fill();
                wCtx.save(); wCtx.rotate(i * arc + arc / 2); wCtx.textAlign = "right"; wCtx.fillStyle = "#fff"; wCtx.font = "bold 13px sans-serif"; wCtx.fillText(slices[i].text, radius - 15, 0); wCtx.restore();
            }
            wCtx.restore(); wCtx.fillStyle = "#f59e0b"; wCtx.beginPath(); wCtx.moveTo(center - 8, 0); wCtx.lineTo(center + 8, 0); wCtx.lineTo(center, 12); wCtx.fill();
        }
        drawWheel(0);

        async function playRealWheel() {
            let bet = parseFloat(document.getElementById('spinBet').value);
            if (isNaN(bet) || bet <= 0 || bet > balance) { alert("পর্যাপ্ত ব্যালেন্স নেই!"); return; }
            await updateBalanceInBackend(-bet);
            let winningIndex = Math.floor(Math.random() * slices.length);
            let sliceAngle = (2 * Math.PI) / slices.length;
            let targetAngle = (2 * Math.PI * 5) + (1.5 * Math.PI) - (winningIndex * sliceAngle + sliceAngle / 2);
            let currentAngle = 0, totalFrames = 40, frame = 0;
            let wheelInterval = setInterval(async () => {
                frame++; currentAngle = targetAngle * (frame / totalFrames); drawWheel(currentAngle);
                if (frame >= totalFrames) {
                    clearInterval(wheelInterval);
                    let mult = parseFloat(slices[winningIndex].text) || 0;
                    if (mult > 0) {
                        let prize = bet * mult; await updateBalanceInBackend(prize);
                        document.getElementById("spinStatus").innerText = `🎉 জিতেছেন ${prize.toFixed(2)} টাকা!`;
                    } else { document.getElementById("spinStatus").innerText = `❌ লস করেছেন!`; }
                }
            }, 30);
        }

        function submitWithdraw() {
            let phone = document.getElementById("witPhone").value;
            let amount = document.getElementById("witAmount").value;
            if (!phone || !amount) { alert("নম্বর ও পরিমাণ দিন!"); return; }
            window.open(`https://t.me/Fastpay8_bot?text=/withdraw%20${phone}%20${amount}`, '_blank');
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/get_balance/<user_id>', methods=['GET'])
def get_balance(user_id):
    if user_id not in user_balances:
        user_balances[user_id] = 100.0
    return jsonify({"status": "success", "balance": user_balances[user_id]})

@app.route('/update_balance', methods=['POST'])
def update_balance():
    data = request.json
    user_id = str(data.get("user_id"))
    amount_diff = float(data.get("amount_diff", 0))
    if user_id not in user_balances:
        user_balances[user_id] = 100.0
    user_balances[user_id] += amount_diff
    if user_balances[user_id] < 0:
        user_balances[user_id] = 0.0
    return jsonify({"status": "success", "new_balance": user_balances[user_id]})

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [[InlineKeyboardButton("🎮 গেম খেলুন (Mini App)", web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user.id}"))]]
    await update.message.reply_text("স্বাগতম! নিচে ক্লিক করে গেম খেলা শুরু করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("সঠিক নিয়ম: /withdraw [বিকাশ নম্বর] [পরিমাণ]")
        return
    await update.message.reply_text(f"✅ উত্তোলনের রিকোয়েস্ট সফল! নম্বর: {args[0]}, পরিমাণ: {args[1]} টাকা")

if __name__ == '__main__':
    import threading
    import asyncio
    
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("withdraw", withdraw))
    
    def run_bot():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        application.run_polling()

    threading.Thread(target=run_bot, daemon=True).start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
