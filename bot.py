import logging
import json
import os
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, filters,
)
from pymongo import MongoClient

# লগিং সেটআপ
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# এনভায়রনমেন্ট ভেরিয়েবল থেকে টোকেন এবং ডাটাবেস লিংক নেওয়া
TOKEN = os.environ.get("BOT_TOKEN", "8713892015:AAFez0mngDbYsAxsl-aE0fQOJqnnvHh5_K8")
ADMIN_ID = 7100342395
BOT_USERNAME = "Fastpay8_bot"

# MongoDB কানেকশন সেটআপ
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://admin:Bashar904@cluster0.nkm8mxx.mongodb.net/?appName=Cluster0")
client = MongoClient(MONGO_URI)
db = client["telegram_bot_db"]
users_collection = db["users"]

pending_withdrawals = {}

# ডাটা ফেচ বা পাওয়ার ফাংশন
def get_user_data(user_id):
    user_data = users_collection.find_one({"user_id": user_id})
    if not user_data:
        user_data = {
            "user_id": user_id,
            "balance": 150.0,
            "referrals": [],
            "referred_by": None,
            "total_deposit": 0.0,
            "total_withdrawal": 0,
            "last_task_date": None,
            "task_streak": 0,
            "task_cycle_start": None,
            "bonus_claimed": False
        }
        users_collection.insert_one(user_data)
    return user_data

def update_user_field(user_id, update_data):
    users_collection.update_one({"user_id": user_id}, {"$set": update_data}, upsert=True)

# --- ফ্লাস্ক (Flask) ওয়েব সার্ভার সেটআপ (মিনি অ্যাপের জন্য) ---
app = Flask(__name__)

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
        .btn { background: #22c55e; color: white; padding: 12px; width: 100%; border: none; border-radius: 10px; cursor: pointer; font-size: 15px; font-weight: bold; transition: 0.2s; }
        .btn:active { transform: scale(0.98); }
        .stop-btn { background: #ef4444 !important; }
        input, select { width: 90%; padding: 10px; margin: 5px; border-radius: 5px; border: none; background: #0f172a; color: white; text-align: center; font-size: 15px; outline: none; }
        
        .game-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 10px; }
        .game-card { background: #334155; padding: 12px; border-radius: 10px; cursor: pointer; font-weight: bold; font-size: 13px; text-align: center; transition: 0.2s; }
        .game-card:active { background: #38bdf8; color: #0b0f19; }
        
        .back-btn { background: #475569; margin-bottom: 8px; padding: 6px 12px; border: none; border-radius: 6px; color: white; cursor: pointer; float: left; font-size: 12px; }
        .game-section { display: none; }
        .active-section { display: block; }
        
        canvas { background: #0b0f19; border-radius: 10px; margin: 5px auto; display: block; }
        .slot-machine-box { background: linear-gradient(135deg, #450a0a, #1e1b4b); border: 2px solid #ef4444; border-radius: 12px; padding: 10px; margin: 10px auto; max-width: 350px; }
        
        .history-bar { display: flex; gap: 5px; justify-content: center; overflow-x: auto; margin-bottom: 8px; padding: 4px; }
        .history-tag { background: #334155; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; color: #38bdf8; }

        .notification-bar {
            background: linear-gradient(90deg, #1e293b, #334155);
            border-left: 4px solid #22c55e;
            padding: 8px 12px;
            border-radius: 8px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            text-align: left;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            overflow: hidden;
            white-space: nowrap;
        }
        .noti-icon { font-size: 15px; }
        .noti-text { color: #38bdf8; font-weight: bold; transition: opacity 0.3s ease-in-out; }
    </style>
</head>
<body>
    <div class="notification-bar">
        <span class="noti-icon">🔔</span>
        <div class="noti-text" id="notiText">পেমেন্ট প্রুফ লোড হচ্ছে...</div>
    </div>

    <div class="box">
        <h4>💰 মূল ব্যালেন্স: <span id="balanceText">0.00</span> টাকা</h4>
    </div>

    <div id="gameLobby" class="game-section active-section box">
        <h3>🎮 প্রো গেম জোন</h3>
        <div class="game-grid" id="gameGrid">
            <div class="game-card" onclick="openGame('rocketGame')">🚀 রকেট ক্র্যাশ</div>
            <div class="game-card" onclick="openGame('slotsGame')">🎰 স্লট মেশিন (৩×৩)</div>
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
        <h3 style="margin:0;">🎰 স্লট মেশিন (৩×৩ ঘর)</h3>
        <canvas id="slotsCanvas" width="350" height="210"></canvas>
        <select id="betMode">
            <option value="single">১টি সারি</option>
            <option value="all">৩টি সারি</option>
        </select>
        <select id="selectedRow">
            <option value="0">⬆ ওপরের সারি</option>
            <option value="1" selected>⏺ মাঝের সারি</option>
            <option value="2">⬇ নিচের সারি</option>
        </select>
        <input type="number" id="slotsBet" value="50" min="1">
        <p id="slotsStatus" style="color: #94a3b8; font-size: 12px; margin: 5px;">স্লট স্পিন করুন</p>
        <button class="btn" id="slotsBtn" onclick="playSlotsGame()">স্লট ঘোড়ান</button>
    </div>

    <div id="boxingGame" class="game-section box">
        <button class="back-btn" onclick="closeGame()">⬅ ব্যাক</button>
        <h3 style="margin:0; color: #f59e0b;">🥊 বক্সিং কিং স্লট</h3>
        <div class="slot-machine-box">
            <canvas id="boxingCanvas" width="330" height="150" style="background:#000; border-radius:8px; margin:0 auto;"></canvas>
        </div>
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
        let userId = urlParams.get('user_id');
        if (!userId && tg.initDataUnsafe && tg.initDataUnsafe.user) {
            userId = tg.initDataUnsafe.user.id;
        }
        if (!userId) userId = "123456789";

        let balance = 0.0;

        async function fetchBalance() {
            try {
                let res = await fetch(`/get_balance/${userId}`);
                let data = await res.json();
                if (data.status === "success") {
                    balance = data.balance;
                    document.getElementById("balanceText").innerText = balance.toFixed(2);
                }
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
                if (data.status === "success") {
                    balance = data.new_balance;
                    document.getElementById("balanceText").innerText = balance.toFixed(2);
                }
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

        const usernames = ["rahim_99", "karim_bd", "tanvir_x", "sakib_pro", "fahim_77", "imon_vip", "hasan_sk", "shanto_007", "nabil_11", "arif_king", "joy_gamer", "fahad_ff", "rifat_999", "mehedi_24", "tanim_boss"];
        const gamesList = ["রকেট ক্র্যাশ", "স্লট মেশিন", "লাকি স্পিন", "বক্সিং কিং"];
        const paymentMethods = ["বিকাশ", "নগদ", "বাইন্যান্স (Binance Pay)"];

        function generateAutoNotification() {
            let user = usernames[Math.floor(Math.random() * usernames.length)] + Math.floor(Math.random() * 90 + 10);
            let game = gamesList[Math.floor(Math.random() * gamesList.length)];
            let method = paymentMethods[Math.floor(Math.random() * paymentMethods.length)];
            let amount = Math.floor(Math.random() * 45 + 5) * 50; 
            
            const types = [
                `🔥 পেমেন্ট প্রুফ: @${user} (${method}) এর মাধ্যমে ${amount} টাকা পেমেন্ট সফল!`,
                `🎉 অভিনন্দন! @${user} (${game}) খেলে ${amount} টাকা উইথড্র করেছেন।`,
                `✅ পেমেন্ট সফল: @${user} - ${amount} টাকা (${method} ক্যাশআউট)`,
                `💰 উইনিং প্রুফ: @${user} ${game} থেকে ${amount} টাকা জিতেছেন!`
            ];
            return types[Math.floor(Math.random() * types.length)];
        }

        function updateNotifications() {
            const notiElement = document.getElementById("notiText");
            if (notiElement) {
                notiElement.style.opacity = 0;
                setTimeout(() => {
                    notiElement.innerText = generateAutoNotification();
                    notiElement.style.opacity = 1;
                }, 300);
            }
        }
        setInterval(updateNotifications, 4000);

        const rocketCanvas = document.getElementById('rocketCanvas');
        const rctx = rocketCanvas.getContext('2d');
        let rocketState = "WAITING", multiplier = 1.00, crashAt = 1.00, rocketBetVal = 0, hasRocketBet = false, isRocketRunning = false, rx = 20, ry = 150;
        let rocketHistory = [];

        function startRocketLoop() {
            isRocketRunning = true;
            rocketState = "WAITING";
            multiplier = 1.00;
            hasRocketBet = false;
            rx = 20; ry = 150;
            let countdown = 7; 
            let timer = setInterval(() => {
                if (!isRocketRunning) { clearInterval(timer); return; }
                if (document.getElementById('rocketGame').classList.contains('active-section')) {
                    drawRocketScene("ফ্লাইট শুরু: " + countdown + "s", "#38bdf8");
                }
                countdown--;
                if (countdown < 0) { clearInterval(timer); launchRealRocket(); }
            }, 1000);
        }

        function launchRealRocket() {
            if (!isRocketRunning) return;
            rocketState = "FLYING";
            let randomValue = Math.random();
            if (randomValue < 0.15) crashAt = parseFloat((Math.random() * 15 + 5).toFixed(2));
            else if (randomValue < 0.45) crashAt = parseFloat((Math.random() * 3 + 2).toFixed(2));
            else if (randomValue < 0.85) crashAt = parseFloat((Math.random() * 0.7 + 1.3).toFixed(2));
            else crashAt = parseFloat((Math.random() * 0.29 + 1.01).toFixed(2));

            if (hasRocketBet) {
                document.getElementById("rocketBtn").innerText = "💰 ক্যাশ আউট করুন";
                document.getElementById("rocketBtn").className = "btn stop-btn";
            }
            
            let flyInterval = setInterval(async () => {
                if (!isRocketRunning || rocketState !== "FLYING") { clearInterval(flyInterval); return; }
                multiplier += (multiplier < 2.0 ? 0.02 : 0.05);
                if (rx < 250) rx += 1.2;
                if (ry > 40) ry -= 0.9;
                
                let autoCashVal = parseFloat(document.getElementById("autoCashInput").value);
                if (hasRocketBet && !isNaN(autoCashVal) && multiplier >= autoCashVal && autoCashVal < crashAt) {
                    await cashOutRocket(autoCashVal);
                }

                if (document.getElementById('rocketGame').classList.contains('active-section')) {
                    drawRocketScene(multiplier.toFixed(2) + "x", "#22c55e");
                }
                
                if (multiplier >= crashAt) {
                    clearInterval(flyInterval);
                    rocketState = "CRASHED";
                    rocketHistory.unshift(crashAt.toFixed(2) + "x");
                    if(rocketHistory.length > 5) rocketHistory.pop();
                    updateRocketHistoryUI();

                    if (document.getElementById('rocketGame').classList.contains('active-section')) {
                        drawRocketScene("💥 ক্র্যাশ " + crashAt + "x", "#ef4444");
                    }
                    if(hasRocketBet) {
                        hasRocketBet = false;
                        document.getElementById("rocketStatus").innerText = "💥 ক্র্যাশ হয়ে গেছে! বেট হেরেছেন।";
                    }
                    document.getElementById("rocketBtn").innerText = "বেট নিশ্চিত করুন";
                    document.getElementById("rocketBtn").className = "btn";
                    setTimeout(startRocketLoop, 3000);
                }
            }, 60);
        }

        function updateRocketHistoryUI() {
            let bar = document.getElementById("rocketHistory");
            bar.innerHTML = rocketHistory.map(h => `<span class="history-tag">${h}</span>`).join('');
        }

        function drawRocketScene(text, color) {
            rctx.clearRect(0, 0, rocketCanvas.width, rocketCanvas.height);
            rctx.strokeStyle = '#1e293b'; rctx.lineWidth = 1;
            rctx.beginPath(); rctx.moveTo(0, 150); rctx.lineTo(350, 150); rctx.stroke();
            if (rocketState === "FLYING") {
                rctx.strokeStyle = '#22c55e'; rctx.lineWidth = 3;
                rctx.beginPath(); rctx.moveTo(20, 150); rctx.lineTo(rx, ry); rctx.stroke();
            }
            rctx.font = "24px sans-serif";
            rctx.fillText(rocketState === "CRASHED" ? "💥" : "🚀", rx, ry);
            rctx.fillStyle = color; rctx.font = "bold 22px sans-serif"; rctx.textAlign = "center";
            rctx.fillText(text, rocketCanvas.width / 2, 40);
        }

        async function cashOutRocket(mult) {
            hasRocketBet = false;
            let win = rocketBetVal * mult;
            await updateBalanceInBackend(win);
            document.getElementById("rocketStatus").innerText = `🎉 অটো ক্যাশ আউট! জিতেছেন ${win.toFixed(2)} টাকা (${mult}x)`;
            let btn = document.getElementById("rocketBtn");
            btn.innerText = "বেট নিশ্চিত করুন";
            btn.className = "btn";
        }

        async function toggleRocketGame() {
            let betInput = document.getElementById("rocketBet");
            let btn = document.getElementById("rocketBtn");
            let status = document.getElementById("rocketStatus");
            if (rocketState === "WAITING") {
                if (hasRocketBet) return;
                rocketBetVal = parseFloat(betInput.value);
                if (isNaN(rocketBetVal) || rocketBetVal <= 0 || rocketBetVal > balance) { alert("সঠিক বেট বা ব্যালেন্স নেই!"); return; }
                await updateBalanceInBackend(-rocketBetVal);
                hasRocketBet = true;
                btn.innerText = "✅ বেট প্লেসড";
                status.innerText = "ফ্লাইট অপেক্ষায়...";
            } else if (rocketState === "FLYING" && hasRocketBet) {
                await cashOutRocket(multiplier);
            }
        }

        const slotsCanvas = document.getElementById('slotsCanvas');
        const slotCtx = slotsCanvas.getContext('2d');

        function drawSlotsGrid(gridData, text) {
            slotCtx.clearRect(0, 0, slotsCanvas.width, slotsCanvas.height);
            let cellWidth = 85, cellHeight = 50, startX = 45, startY = 10;
            slotCtx.font = "26px sans-serif"; slotCtx.textAlign = "center"; slotCtx.textBaseline = "middle";
            for (let r = 0; r < 3; r++) {
                for (let c = 0; c < 3; c++) {
                    let bx = startX + c * (cellWidth + 10);
                    let by = startY + r * (cellHeight + 8);
                    slotCtx.fillStyle = '#0f172a'; slotCtx.fillRect(bx, by, cellWidth, cellHeight);
                    slotCtx.strokeStyle = '#38bdf8'; slotCtx.lineWidth = 1.5; slotCtx.strokeRect(bx, by, cellWidth, cellHeight);
                    slotCtx.fillText(gridData[r][c], bx + cellWidth / 2, by + cellHeight / 2);
                }
            }
            slotCtx.fillStyle = "#38bdf8"; slotCtx.font = "bold 13px sans-serif";
            slotCtx.fillText(text, slotsCanvas.width / 2, 185);
        }

        async function playSlotsGame() {
            let bet = parseFloat(document.getElementById('slotsBet').value);
            let mode = document.getElementById('betMode').value;
            let chosenRow = parseInt(document.getElementById('selectedRow').value);
            let btn = document.getElementById('slotsBtn');
            if (isNaN(bet) || bet <= 0 || bet > balance) { alert("পর্যাপ্ত ব্যালেন্স নেই!"); return; }
            btn.disabled = true;
            await updateBalanceInBackend(-bet);
            let icons = ['🍒', '🍋', '🔔', '⭐', '💎', '🍉'], count = 0;
            let interval = setInterval(async () => {
                count++;
                let randomGrid = Array.from({length:3}, ()=>Array.from({length:3}, ()=>icons[Math.floor(Math.random()*icons.length)]));
                drawSlotsGrid(randomGrid, "স্লট রোল হচ্ছে...");
                if (count > 12) {
                    clearInterval(interval);
                    btn.disabled = false;
                    let finalGrid = Array.from({length:3}, ()=>Array.from({length:3}, ()=>icons[Math.floor(Math.random()*icons.length)]));
                    let multiplier = 0, message = "❌ মিল হয়নি, হেরে গেছেন।";
                    if (Math.random() < 0.35) { 
                        multiplier = 2; message = "🎉 ২ গুণ জিতেছেন!";
                        let winIcon = icons[Math.floor(Math.random() * icons.length)];
                        let winRow = (mode === 'single') ? chosenRow : 1;
                        finalGrid[winRow] = [winIcon, winIcon, winIcon];
                    }
                    if (multiplier > 0) {
                        let prize = bet * multiplier;
                        await updateBalanceInBackend(prize);
                    }
                    drawSlotsGrid(finalGrid, message);
                }
            }, 70);
        }

        const boxingCanvas = document.getElementById('boxingCanvas');
        const bCtx = boxingCanvas.getContext('2d');
        function drawBoxing(symbols, text) {
            bCtx.clearRect(0, 0, boxingCanvas.width, boxingCanvas.height);
            bCtx.fillStyle = '#0f172a'; bCtx.fillRect(40, 30, 250, 70);
            bCtx.strokeStyle = '#ef4444'; bCtx.lineWidth = 2; bCtx.strokeRect(40, 30, 250, 70);
            bCtx.font = "30px sans-serif"; bCtx.textAlign = "center";
            bCtx.fillText(symbols[0], 90, 75); bCtx.fillText(symbols[1], 165, 75); bCtx.fillText(symbols[2], 240, 75);
            bCtx.fillStyle = "#f59e0b"; bCtx.font = "bold 13px sans-serif";
            bCtx.fillText(text, boxingCanvas.width / 2, 130);
        }
        async function playBoxingGame() {
            let bet = parseFloat(document.getElementById('boxingBet').value);
            let status = document.getElementById('boxingStatus');
            if (isNaN(bet) || bet <= 0 || bet > balance) { alert("বেট চেক করুন বা ব্যালেন্স কম আছে!"); return; }
            await updateBalanceInBackend(-bet);
            let icons = ['🥊', '🥋', '🏆', '⭐', '🔥', '👑'], count = 0;
            let interval = setInterval(async () => {
                count++;
                drawBoxing([icons[Math.floor(Math.random()*6)], icons[Math.floor(Math.random()*6)], icons[Math.floor(Math.random()*6)]], "🥊 রিং-এ ফাইট চলছে...");
                if (count > 12) {
                    clearInterval(interval);
                    let win = Math.random() < 0.20;
                    if (win) {
                        let prize = bet * 3;
                        await updateBalanceInBackend(prize);
                        drawBoxing(['👑', '👑', '👑'], `🎉 নকআউট জয়! জিতেছেন ${prize.toFixed(2)} টাকা!`);
                        status.innerText = `বিজয় লাভ করেছেন!`;
                    } else {
                        drawBoxing(['🥊', '🥋', '⭐'], "❌ হেরে গেছেন, আবার চেষ্টা করুন।");
                        status.innerText = `হেরে গেছেন!`;
                    }
                }
            }, 70);
        }

        const wheelCanvas = document.getElementById('realWheelCanvas');
        const wCtx = wheelCanvas.getContext('2d');
        const slices = [
            { text: "2x", color: "#22c55e" }, { text: "0x", color: "#ef4444" },
            { text: "3x", color: "#38bdf8" }, { text: "0x", color: "#ef4444" },
            { text: "1.5x", color: "#f59e0b" }, { text: "0x", color: "#ef4444" },
            { text: "0x", color: "#ef4444" }, { text: "5x", color: "#eab308" }
        ];

        function drawWheel(angle) {
            let width = wheelCanvas.width, height = wheelCanvas.height, center = width / 2, radius = center - 15;
            wCtx.clearRect(0, 0, width, height);
            wCtx.save(); wCtx.translate(center, center); wCtx.rotate(angle);
            let arc = (2 * Math.PI) / slices.length;
            for (let i = 0; i < slices.length; i++) {
                wCtx.beginPath(); wCtx.fillStyle = slices[i].color; wCtx.moveTo(0, 0);
                wCtx.arc(0, 0, radius, i * arc, (i + 1) * arc); wCtx.lineTo(0, 0); wCtx.fill();
                wCtx.strokeStyle = "#0b0f19"; wCtx.lineWidth = 2; wCtx.stroke();
                wCtx.save(); wCtx.rotate(i * arc + arc / 2); wCtx.textAlign = "right"; wCtx.textBaseline = "middle";
                wCtx.fillStyle = "#fff"; wCtx.font = "bold 13px sans-serif"; wCtx.fillText(slices[i].text, radius - 15, 0);
                wCtx.restore();
            }
            wCtx.restore();
            wCtx.fillStyle = "#f59e0b"; wCtx.beginPath();
            wCtx.moveTo(center - 8, 0); wCtx.lineTo(center + 8, 0); wCtx.lineTo(center, 12); wCtx.fill();
        }

        async function playRealWheel() {
            let bet = parseFloat(document.getElementById('spinBet').value);
            let status = document.getElementById('spinStatus');
            let spinBtn = document.getElementById('spinBtn');
            if (isNaN(bet) || bet <= 0 || bet > balance) { alert("সঠিক বেট বা পর্যাপ্ত ব্যালেন্স নেই!"); return; }
            spinBtn.disabled = true;
            await updateBalanceInBackend(-bet);
            status.innerText = "🎡 চাকা ঘুরছে...";
            let winningIndex = Math.floor(Math.random() * slices.length);
            let sliceAngle = (2 * Math.PI) / slices.length;
            let targetAngle = (2 * Math.PI * 6) + (1.5 * Math.PI) - (winningIndex * sliceAngle + sliceAngle / 2);
            let currentAngle = 0, totalFrames = 60, frame = 0;
            let wheelInterval = setInterval(async () => {
                frame++;
                let progress = frame / totalFrames;
                currentAngle = targetAngle * (1 - Math.pow(1 - progress, 3));
                drawWheel(currentAngle);
                if (frame >= totalFrames) {
                    clearInterval(wheelInterval);
                    spinBtn.disabled = false;
                    let result = slices[winningIndex].text;
                    let mult = parseFloat(result) || 0;
                    if (mult > 0) {
                        let prize = bet * mult;
                        await updateBalanceInBackend(prize);
                        status.innerText = `🎉 অভিনন্দন! জিতেছেন ${prize.toFixed(2)} টাকা (${result})`;
                    } else {
                        status.innerText = `❌ ফলাফল: ${result}। আপনি লস করেছেন!`;
                    }
                }
            }, 30);
        }

        function submitWithdraw() {
            let phone = document.getElementById("witPhone").value;
            let amount = document.getElementById("witAmount").value;
            if (!phone || !amount) { alert("বিকাশ নম্বর ও পরিমাণ প্রদান করুন!"); return; }
            window.open(`https://t.me/Fastpay8_bot?text=/withdraw%20${phone}%20${amount}`, '_blank');
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/get_balance/<int:user_id>')
def get_balance(user_id):
    user_data = get_user_data(user_id)
    return jsonify({"status": "success", "balance": round(user_data.get("balance", 150.0), 2)})

@app.route('/update_balance', methods=['POST'])
def update_balance():
    try:
        data = request.get_json()
        user_id = int(data.get("user_id"))
        amount_diff = float(data.get("amount_diff"))
        
        user_data = get_user_data(user_id)
        current_balance = user_data.get("balance", 150.0)
        new_balance = round(current_balance + amount_diff, 2)
        
        if new_balance < 0:
            new_balance = 0.0
            
        update_user_field(user_id, {"balance": new_balance})
        
        return jsonify({"status": "success", "new_balance": new_balance})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


# --- টেলিগ্রাম বট হ্যান্ডলার্স ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_data = users_collection.find_one({"user_id": user_id})
    is_new_user = False
    
    if not user_data:
        user_data = {
            "user_id": user_id,
            "balance": 150.0,
            "referrals": [],
            "referred_by": None,
            "total_deposit": 0.0,
            "total_withdrawal": 0,
            "last_task_date": None,
            "task_streak": 0,
            "task_cycle_start": None,
            "bonus_claimed": False
        }
        users_collection.insert_one(user_data)
        is_new_user = True
        
    if context.args and is_new_user:
        payload = context.args[0]
        if payload.startswith("ref_"):
            try:
                referrer_id = int(payload.split("_")[1])
                if referrer_id != user_id:
                    ref_user = get_user_data(referrer_id)
                    referrals_list = ref_user.get("referrals", [])
                    if user_id not in referrals_list:
                        referrals_list.append(user_id)
                        new_ref_balance = round(ref_user.get("balance", 0.0) + 100.0, 2)
                        update_user_field(referrer_id, {
                            "referrals": referrals_list,
                            "balance": new_ref_balance
                        })
                        update_user_field(user_id, {"referred_by": referrer_id})
                        await context.bot.send_message(
                            referrer_id, 
                            "🎉 অভিনন্দন! আপনার রেফারল লিংকে নতুন একজন ইউজার যুক্ত হয়েছে এবং আপনি রেফার বোনাস হিসেবে ১০০ টাকা পেয়েছেন!"
                        )
            except ValueError:
                pass
    
    web_app_url = "https://telegram-bot-oh28.onrender.com"
    
    keyboard_inline = [
        [InlineKeyboardButton("🎮 গেম খেলুন (Mini App)", web_app={"url": web_app_url})]
    ]
    
    current_balance = round(user_data.get("balance", 150.0), 2)
    reply_markup_inline = InlineKeyboardMarkup(keyboard_inline)
    
    keyboard = [
        ["👤 প্রোফাইল", "💰 ব্যালেন্স"],
        ["📥 জমা", "📤 উত্তোলন"],
        ["🔗 রেফার লিংক", "🎁 ডেইলি টাস্ক"]
    ]
    
    await update.message.reply_text(
        f"স্বাগতম, {user.first_name}! আপনার বর্তমান ব্যালেন্স {current_balance} টাকা। অপশন বেছে নিন:", 
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    await update.message.reply_text(
        "👇 নিচে গেম খেলে আয় করতে বাটন সিলেক্ট করুন:", 
        reply_markup=reply_markup_inline
    )

async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    parts = text.replace("/deposit", "").strip().split()
    
    if len(parts) < 2:
        await update.message.reply_text("সঠিক নিয়ম: /deposit <পরিমাণ> <TrxID>\nউদাহরণ: /deposit 200 ABC123XYZ")
        return
        
    amount_str, trx = parts[0], parts[1]
    try:
        amount = float(amount_str)
        if amount <= 0: raise ValueError()
    except ValueError:
        await update.message.reply_text("❌ জমার পরিমাণ সঠিক সংখ্যা হতে হবে। উদাহরণ: /deposit 200 TrxID")
        return

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"dep_approve_{user.id}_{amount}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"dep_reject_{user.id}_{amount}")
        ]
    ]
    try:
        await context.bot.send_message(
            ADMIN_ID, 
            f"📥 নতুন বিকাশ জমা রিকোয়েস্ট!\n👤 ইউজার: {user.first_name}\n💰 পরিমাণ: {amount}\n🆔 TrxID: {trx}", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await update.message.reply_text("✅ আপনার জমা রিকোয়েস্ট অ্যাডমিনের কাছে পাঠানো হয়েছে।")
    except Exception as e:
        await update.message.reply_text("❌ দুঃখিত, রিকোয়েস্ট পাঠাতে সমস্যা হয়েছে।")

# বাইন্যান্স (Binance) জমা কমান্ড (১ ডলার = ১২৬ টাকা উল্লেখসহ)
async def binance_deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    parts = text.replace("/binancedeposit", "").strip().split()
    
    if len(parts) < 2:
        await update.message.reply_text("সঠিক নিয়ম: /binancedeposit <ইউএসডিটি_পরিমাণ> <Binance_Pay_ID>\nউদাহরণ: /binancedeposit 10 123456789\n*(নোট: ১ ডলার = ১২৬ টাকা হিসেবে মোট টাকা যোগ হবে)*")
        return
        
    usdt_str, binance_id = parts[0], parts[1]
    try:
        usdt_amount = float(usdt_str)
        if usdt_amount <= 0: raise ValueError()
    except ValueError:
        await update.message.reply_text("❌ জমার পরিমাণ সঠিক সংখ্যা হতে হবে।")
        return

    # ১ ডলার = ১২৬ টাকা হিসাব করে মোট টাকা বের করা
    amount = usdt_amount * 126

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"dep_approve_{user.id}_{amount}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"dep_reject_{user.id}_{amount}")
        ]
    ]
    try:
        await context.bot.send_message(
            ADMIN_ID, 
            f"🟡 নতুন বাইন্যান্স (Binance Pay) জমা রিকোয়েস্ট!\n👤 ইউজার: {user.first_name} (`{user.id}`)\n💵 ইউএসডিটি: {usdt_amount} $\n💰 সমপরিমাণ টাকা (১$ = ১২৬৳): {amount} টাকা\n🆔 Binance Pay ID: {binance_id}", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await update.message.reply_text(f"✅ আপনার বাইন্যান্স জমা রিকোয়েস্ট অ্যাডমিনের কাছে পাঠানো হয়েছে। ({usdt_amount}$ = {amount} টাকা)")
    except Exception as e:
        await update.message.reply_text("❌ দুঃখিত, রিকোয়েস্ট পাঠাতে সমস্যা হয়েছে।")

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    parts = text.replace("/withdraw", "").strip().split()
    
    if len(parts) < 2:
        await update.message.reply_text("সঠিক নিয়ম: /withdraw <নম্বর> <পরিমাণ>\nউদাহরণ: /withdraw 017 1200")
        return
        
    try:
        phone = parts[0]
        amount = float(parts[1])
    except ValueError:
        await update.message.reply_text("❌ ভুল ফরম্যাট! সঠিক নিয়মে লিখুন: /withdraw <নম্বর> <পরিমাণ>")
        return

    if amount < 1200:
        await update.message.reply_text("❌ মিনিমাম উত্তোলন ১২০০ টাকা।")
        return
        
    user_data = get_user_data(user.id)
    current_balance = user_data.get("balance", 0.0)
    
    if current_balance < amount:
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.id}"
        await update.message.reply_text(f"❌ আপনার পর্যাপ্ত পরিমাণে টাকা নাই!\n🔗 বেশি বেশি রেফার করুন:\n{ref_link}")
        return

    referrals_list = user_data.get("referrals", [])
    if len(referrals_list) < 2:
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.id}"
        await update.message.reply_text(f"❌ উত্তোলন করতে হলে কমপক্ষে **২ টি সফল রেফার** থাকতে হবে!\n👥 বর্তমান রেফার: {len(referrals_list)} জন\n🔗 লিংক:\n{ref_link}")
        return

    total_dep = user_data.get("total_deposit", 0.0)
    if total_dep < 200:
        await update.message.reply_text("❌ উত্তোলন করতে হলে কমপক্ষে **২০০ টাকা জমা** করতে হবে!")
        return

    pending_withdrawals[user.id] = {"phone": phone, "amount": amount}
    keyboard = [
        [
            InlineKeyboardButton("🔴 বিকাশ (Bkash)", callback_data=f"method_bkash_{user.id}"),
            InlineKeyboardButton("🟠 নগদ (Nagad)", callback_data=f"method_nagad_{user.id}")
        ]
    ]
    await update.message.reply_text("📲 আপনি কোন মাধ্যমে টাকা নিতে চান তা সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

async def total_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID: return
    try:
        total_count = users_collection.count_documents({})
        await update.message.reply_text(f"📊 বট স্ট্যাটিস্টিক্স\n👥 মোট রেজিস্টার্ড ইউজার: **{total_count}** জন")
    except Exception as e:
        await update.message.reply_text(f"❌ সমস্যা: {str(e)}")

async def userlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID: return
    try:
        all_users = list(users_collection.find())
        if not all_users:
            await update.message.reply_text("❌ কোনো ইউজার পাওয়া যায়নি।")
            return
            
        await update.message.reply_text("⏳ ইউজার লিস্ট চেক করা হচ্ছে এবং ব্লক ইউজারদের ক্লিন করা হচ্ছে...")
        
        valid_users = []
        deleted_count = 0

        for u in all_users:
            target_user_id = u.get('user_id')
            try:
                await context.bot.send_chat_action(chat_id=target_user_id, action="typing")
                valid_users.append(u)
            except Exception as e:
                error_str = str(e).lower()
                if "blocked" in error_str or "forbidden" in error_str or "chat not found" in error_str:
                    users_collection.delete_one({"user_id": target_user_id})
                    deleted_count += 1
                else:
                    valid_users.append(u)

        if not valid_users:
            await update.message.reply_text(f"❌ কোনো সক্রিয় ইউজার নেই। {deleted_count}টি ব্লক করা ইউজার ডিলিট করা হয়েছে।")
            return

        await update.message.reply_text(f"📋 **সক্রিয় ইউজারের তথ্য (মোট: {len(valid_users)} জন, ডিলিট হয়েছে: {deleted_count} জন):**")
        chunk_text = ""
        for idx, u in enumerate(valid_users, 1):
            line = f"{idx}. আইডি: `{u.get('user_id')}`\n   💰 ব্যালেন্স: {round(u.get('balance', 0.0), 2)}৳ | জমা: {round(u.get('total_deposit', 0.0), 2)}৳ | রেফার: {len(u.get('referrals', []))}\n\n"
            if len(chunk_text) + len(line) > 3500:
                await update.message.reply_text(chunk_text, parse_mode="Markdown")
                chunk_text = ""
            chunk_text += line
        if chunk_text:
            await update.message.reply_text(chunk_text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ সমস্যা: {str(e)}")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    message_text = update.message.text.replace("/broadcast", "").strip()
    if not message_text:
        await update.message.reply_text("❌ সঠিক নিয়মে লিখুন:\n`/broadcast আপনার নোটিফিকেশন মেসেজ`", parse_mode="Markdown")
        return

    try:
        all_users = list(users_collection.find({}, {"user_id": 1}))
        success_count = 0
        fail_count = 0
        deleted_count = 0

        await update.message.reply_text("⏳ সবার কাছে নোটিফিকেশন পাঠানো এবং ব্লক ইউজারদের ক্লিন করা শুরু হয়েছে...")

        for u in all_users:
            target_user_id = u.get("user_id")
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"📢 **অফিসিয়াল নোটিফিকেশন**\n\n{message_text}",
                    parse_mode="Markdown"
                )
                success_count += 1
            except Exception as e:
                fail_count += 1
                error_str = str(e).lower()
                if "blocked" in error_str or "forbidden" in error_str or "chat not found" in error_str:
                    users_collection.delete_one({"user_id": target_user_id})
                    deleted_count += 1

        await update.message.reply_text(
            f"✅ **ব্রডকাস্ট ও ক্লিনআপ সম্পন্ন!**\n\n"
            f"📤 সফলভাবে পাঠানো হয়েছে: {success_count} জন\n"
            f"❌ ব্যর্থ হয়েছে: {fail_count} জন\n"
            f"🗑️ ব্লক করা ইউজার ডিলিট করা হয়েছে: {deleted_count} জন"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ সমস্যা হয়েছে: {str(e)}")

async def add_bonus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    try:
        all_users = list(users_collection.find())
        success_count = 0

        await update.message.reply_text("⏳ সকল ইউজারের ব্যালেন্সে ৩০০ টাকা করে যোগ করা হচ্ছে...")

        for u in all_users:
            target_user_id = u.get("user_id")
            current_bal = u.get("balance", 0.0)
            new_bal = round(current_bal + 300.0, 2)
            
            users_collection.update_one({"user_id": target_user_id}, {"$set": {"balance": new_bal}})
            success_count += 1

            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="🎁 **বিশাল উপহার বা বোনাস!**\n\nঅফিসিয়াল ঘোষণা অনুযায়ী আপনার অ্যাকাউন্টে সফলভাবে **৩০০ টাকা স্পেশাল বোনাস** যোগ করা হয়েছে! 💰\n\nএখনই গেম খেলে ইনকাম শুরু করুন।",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        await update.message.reply_text(f"✅ সফলভাবে মোট {success_count} জন ইউজারের ব্যালেন্সে ৩০০ টাকা করে যোগ করা হয়েছে!")
    except Exception as e:
        await update.message.reply_text(f"❌ সমস্যা হয়েছে: {str(e)}")

async def handle_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    text = update.message.text.strip()
    user = update.effective_user
    
    user_data = get_user_data(user.id)
    
    if "প্রোফাইল" in text:
        refs_count = len(user_data.get("referrals", []))
        total_dep = round(user_data.get("total_deposit", 0.0), 2)
        bal = round(user_data.get("balance", 150.0), 2)
        profile_text = f"👤 প্রোফাইল\n🆔 আইডি: {user.id}\n💰 ব্যালেন্স: {bal} টাকা\n📥 মোট জমা: {total_dep} টাকা\n👥 মোট রেফার: {refs_count} জন"
        await update.message.reply_text(profile_text)
    elif "ব্যালেন্স" in text:
        bal = round(user_data.get("balance", 150.0), 2)
        await update.message.reply_text(f"💰 বর্তমান ব্যালেন্স: {bal} টাকা")
    elif "জমা" in text:
        await update.message.reply_text(
            "📥 টাকা অথবা বাইন্যান্সের মাধ্যমে জমা করুন:\n\n"
            "🔴 **বিকাশ মার্চেন্ট:** `01919130118`\n"
            "নিয়ম: `/deposit <পরিমাণ> <TrxID>`\n\n"
            "🟡 **বাইন্যান্স পে (Binance Pay ID):**\n"
            "বাইন্যান্স আইডি: `আপনার_বাইন্যান্স_আইডি_এখানে_দিন`\n"
            "*(রেট: ১ ডলার = ১২৬ টাকা)*\n"
            "নিয়ম: `/binancedeposit <ইউএসডিটি_পরিমাণ> <Binance_Pay_ID>`",
            parse_mode="Markdown"
        )
    elif "উত্তোলন" in text:
        await update.message.reply_text("উত্তোলন নিয়ম: /withdraw <নম্বর> <পরিমাণ>")
    elif "রেফার" in text or "লিংক" in text:
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.id}"
        await update.message.reply_text(f"🔗 আপনার রেফারেল লিংক:\n{ref_link}\n🎁 রেফারে পাবেন ১০০ টাকা বোনাস!")
    elif "ডেইলি টাস্ক" in text:
        now = datetime.utcnow()
        last_date = user_data.get("last_task_date")
        streak = user_data.get("task_streak", 0)
        cycle_start = user_data.get("task_cycle_start")
        
        if cycle_start:
            if isinstance(cycle_start, str): cycle_start = datetime.fromisoformat(cycle_start)
            if now - cycle_start > timedelta(days=7): streak, cycle_start = 0, now
        else: cycle_start = now

        if last_date:
            if isinstance(last_date, str): last_date = datetime.fromisoformat(last_date)
            if now - last_date < timedelta(hours=24):
                time_left = timedelta(hours=24) - (now - last_date)
                hours, remainder = divmod(int(time_left.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                await update.message.reply_text(f"⏳ আজকের টাস্ক সম্পন্ন হয়েছে! অপেক্ষা করুন: {hours} ঘণ্টা {minutes} মিনিট।")
                return

        if streak >= 7: streak, cycle_start = 0, now
        streak += 1
        reward = 30.0 if streak == 7 else 20.0
        new_balance = round(user_data.get("balance", 150.0) + reward, 2)
        
        update_user_field(user.id, {
            "balance": new_balance, "task_streak": streak,
            "last_task_date": now.isoformat(), "task_cycle_start": cycle_start.isoformat() if isinstance(cycle_start, datetime) else cycle_start
        })
        await update.message.reply_text(f"🎁 ডেইলি টাস্ক সম্পন্ন! বোনাস: **{reward} টাকা** (দিন {streak}/7)")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data_parts = query.data.split("_")
    
    if data_parts[0] == "method":
        method = data_parts[1].capitalize()
        target_id = int(data_parts[2])
        if target_id not in pending_withdrawals:
            await query.edit_message_text("❌ সময়সীমা শেষ।")
            return
        wit_data = pending_withdrawals.pop(target_id)
        keyboard = [[InlineKeyboardButton("✅ Approve", callback_data=f"wit_approve_{target_id}_{wit_data['amount']}"), InlineKeyboardButton("❌ Reject", callback_data=f"wit_reject_{target_id}_{wit_data['amount']}")]]
        await context.bot.send_message(ADMIN_ID, f"📤 উত্তোলন রিকোয়েস্ট!\n👤 ইউজার: {target_id}\n💳 মাধ্যম: {method}\n📞 নম্বর: {wit_data['phone']}\n💰 পরিমাণ: {wit_data['amount']}", reply_markup=InlineKeyboardMarkup(keyboard))
        await query.edit_message_text(f"✅ মাধ্যম ({method}) সিলেক্ট হয়েছে।")
        return

    action_type, status, target_id, amount = data_parts[0], data_parts[1], int(data_parts[2]), float(data_parts[3])
    user_data = get_user_data(target_id)
    
    if action_type == "dep":
        if status == "approve":
            new_bal = round(user_data.get("balance", 150.0) + amount, 2)
            new_dep = round(user_data.get("total_deposit", 0.0) + amount, 2)
            update_user_field(target_id, {"balance": new_bal, "total_deposit": new_dep})
            await query.edit_message_text("✅ জমা এপ্রুভড।")
            await context.bot.send_message(target_id, f"🎉 আপনার {amount} টাকা জমা সফল হয়েছে!")
        else:
            await query.edit_message_text("❌ জমা রিজেক্টড।")
            await context.bot.send_message(target_id, f"❌ আপনার {amount} টাকা জমা বাতিল হয়েছে।")
    elif action_type == "wit":
        if status == "approve":
            new_bal = round(max(0.0, user_data.get("balance", 150.0) - amount), 2)
            update_user_field(target_id, {"balance": new_bal, "total_withdrawal": user_data.get("total_withdrawal", 0) + 1})
            await query.edit_message_text("✅ উত্তোলন এপ্রুভড।")
            await context.bot.send_message(target_id, f"✅ আপনার {amount} টাকা পেমেন্ট দেওয়া হয়েছে!")
        else:
            await query.edit_message_text("❌ উত্তোলন রিজেক্টড।")
            await context.bot.send_message(target_id, f"❌ আপনার {amount} টাকা উত্তোলন রিজেক্ট করা হয়েছে।")

def main():
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    app_bot = ApplicationBuilder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("deposit", deposit_command))
    app_bot.add_handler(CommandHandler("binancedeposit", binance_deposit_command))
    app_bot.add_handler(CommandHandler("withdraw", withdraw_command))
    app_bot.add_handler(CommandHandler("totalusers", total_users_command))
    app_bot.add_handler(CommandHandler("userlist", userlist_command))
    app_bot.add_handler(CommandHandler("broadcast", broadcast_command))
    app_bot.add_handler(CommandHandler("addbonus", add_bonus_command))
    app_bot.add_handler(CallbackQueryHandler(button_click))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_request))
    
    print("বট এবং ফ্লাস্ক সার্ভার (১ ডলার = ১২৬ টাকা রেটসহ) সফলভাবে চালু হয়েছে...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
