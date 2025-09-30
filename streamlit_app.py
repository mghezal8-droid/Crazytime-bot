# streamlit_app.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import random
from datetime import datetime
from typing import List, Dict

st.set_page_config(page_title="Crazy Time Bot", layout="wide")

# -----------------------
# CONFIG / CONSTANTES
# -----------------------
MIN_BETS = [0.2, 0.4, 1, 2, 4, 10]

WHEEL = {
    "1": (21, 2),       # payout = multiplier (inclut remise)
    "2": (13, 3),
    "5": (7, 6),
    "10": (4, 11),
    "CoinFlip": (4, 0), # bonus -> gestion séparée
    "Pachinko": (3, 0),
    "CashHunt": (2, 0),
    "CrazyTime": (1, 0)
}

BONUS_MULTIPLIERS = {
    "CoinFlip": 2.5,
    "Pachinko": 3,
    "CashHunt": 4,
    "CrazyTime": 5
}

WHEEL_LIST = [k for k,(c,_) in WHEEL.items() for _ in range(c)]

def adjust_to_minimum(stake: float) -> float:
    for m in MIN_BETS:
        if stake <= m:
            return m
    return MIN_BETS[-1]

# -----------------------
# BOT LOGIC (identique à ta logique demandée)
# -----------------------
class CrazyTimeBot:
    def __init__(self, bankroll: float):
        self.bankroll = bankroll
        self.last_bonus = None
        self.martingale_step_1 = 0
        self.martingale_bet_1 = MIN_BETS[0]

    def suggest_bet(self, past_results: List[str]) -> Dict[str, float]:
        bet_suggestion = {}
        last_spin = past_results[-1] if past_results else None

        # Martingale sur 1
        if last_spin == "1":
            self.martingale_step_1 = 0
            self.martingale_bet_1 = MIN_BETS[0]
        else:
            self.martingale_step_1 += 1
            self.martingale_bet_1 = min(adjust_to_minimum(self.martingale_bet_1 * 2), self.bankroll)
        if self.bankroll >= self.martingale_bet_1:
            bet_suggestion["1"] = self.martingale_bet_1

        # God Mode sur 2,5,10 + bonus (exclut dernier bonus)
        god_targets = ["2","5","10"]
        remaining_bankroll = max(self.bankroll - sum(bet_suggestion.values()), 0)
        if remaining_bankroll >= MIN_BETS[0]:
            portion = remaining_bankroll / len(god_targets)
            for t in god_targets:
                bet_suggestion[t] = adjust_to_minimum(portion)
            for b in ["CoinFlip","Pachinko","CashHunt","CrazyTime"]:
                if b != self.last_bonus:
                    bet_suggestion[b] = adjust_to_minimum(portion / 2)

        # 1 + Bonus Combo (ajoute 1 unité min sur 1 et sur les bonus non répétés)
        remaining_bankroll = max(self.bankroll - sum(bet_suggestion.values()), 0)
        if remaining_bankroll >= MIN_BETS[0]:
            bet_suggestion["1"] = bet_suggestion.get("1", 0) + MIN_BETS[0]
            for b in ["CoinFlip","Pachinko","CashHunt","CrazyTime"]:
                if b != self.last_bonus:
                    bet_suggestion[b] = bet_suggestion.get(b, 0) + MIN_BETS[0]

        # si aucune mise (trop peu), retourne {}
        if sum(bet_suggestion.values()) < MIN_BETS[0]:
            return {}
        return bet_suggestion

    def apply_spin(self, spin_result: str, bet_suggestion: Dict[str, float]) -> Dict:
        total_bet = sum(bet_suggestion.values())
        win_amount = 0.0
        hit = False
        for tgt, stake in bet_suggestion.items():
            if tgt == spin_result:
                if tgt in ["1","2","5","10"]:
                    multiplier = WHEEL[tgt][1]
                    win_amount += stake * multiplier
                else:
                    multiplier = BONUS_MULTIPLIERS.get(tgt, 0)
                    win_amount += stake * multiplier
                hit = True

        result = {
            "timestamp": datetime.now().isoformat(timespec='seconds'),
            "spin": spin_result,
            "total_bet": round(total_bet, 2),
            "win_amount": round(win_amount, 2),
            "bankroll_before": round(self.bankroll, 2),
            "bankroll_after": None,
            "outcome": "HIT" if hit else "LOSS"
        }
        # update bankroll
        self.bankroll = self.bankroll - total_bet + win_amount
        result["bankroll_after"] = round(self.bankroll, 2)

        # update last bonus & martingale reset
        if spin_result in ["CoinFlip","Pachinko","CashHunt","CrazyTime"]:
            self.last_bonus = spin_result
        if spin_result == "1":
            self.martingale_step_1 = 0
            self.martingale_bet_1 = MIN_BETS[0]

        return result

# -----------------------
# SESSION STATE INIT
# -----------------------
if "bot" not in st.session_state:
    st.session_state.bot = None
if "history_df" not in st.session_state:
    st.session_state.history_df = pd.DataFrame(columns=[
        "timestamp","spin","total_bet","win_amount","bankroll_before","bankroll_after","outcome"
    ])
if "past_results" not in st.session_state:
    st.session_state.past_results = []

# -----------------------
# SIDEBAR : paramètres
# -----------------------
with st.sidebar:
    st.header("Paramètres session")
    if st.session_state.bot is None:
        initial_bankroll = st.number_input("Bankroll initiale ($)", min_value=100.0, max_value=200.0, value=120.0, step=5.0)
    else:
        initial_bankroll = st.session_state.bot.bankroll
    if st.button("Nouvelle session / Reset"):
        st.session_state.bot = CrazyTimeBot(bankroll=initial_bankroll)
        st.session_state.history_df = st.session_state.history_df.iloc[0:0]
        st.session_state.past_results = []
        st.experimental_rerun()

    st.markdown("---")
    st.write("Importer un historique de spins (CSV, colonne: spin)")
    uploaded = st.file_uploader("CSV historique (optionnel)", type=["csv"])
    if uploaded:
        try:
            df_up = pd.read_csv(uploaded)
            if "spin" in df_up.columns:
                st.session_state.past_results = df_up["spin"].astype(str).tolist()
                st.success(f"{len(st.session_state.past_results)} spins importés")
            else:
                st.error("CSV doit contenir une colonne 'spin'")
        except Exception as e:
            st.error("Erreur import CSV: " + str(e))

# -----------------------
# INIT BOT si besoin
# -----------------------
if st.session_state.bot is None:
    st.session_state.bot = CrazyTimeBot(bankroll=initial_bankroll)

bot = st.session_state.bot

# -----------------------
# MAIN - UI
# -----------------------
st.title("Crazy Time — Bot de suggestion")
col1, col2 = st.columns([1,2])

with col1:
    st.subheader("Contrôles rapides")
    st.markdown("Clique sur le bouton correspondant au résultat réel du spin (ou importe l'historique).")
    btn_cols = st.columns(2)
    # boutons pour nombres
    if btn_cols[0].button("1"):
        spin_input = "1"
    else:
        spin_input = None
    if btn_cols[1].button("2"):
        spin_input = "2" if spin_input is None else spin_input

    btn_cols2 = st.columns(2)
    if btn_cols2[0].button("5"):
        spin_input = "5"
    if btn_cols2[1].button("10"):
        spin_input = "10"

    st.markdown("**Bonus**")
    b1, b2, b3, b4 = st.columns(4)
    if b1.button("CoinFlip"):
        spin_input = "CoinFlip"
    if b2.button("Pachinko"):
        spin_input = "Pachinko"
    if b3.button("CashHunt"):
        spin_input = "CashHunt"
    if b4.button("CrazyTime"):
        spin_input = "CrazyTime"

    st.markdown("---")
    st.write(f"Bankroll actuelle: **{bot.bankroll:.2f}$**")
    st.write(f"Dernier bonus (exclu): **{bot.last_bonus or '—'}**")

with col2:
    st.subheader("Suggestion de mise pour le prochain spin")
    suggestion = bot.suggest_bet(st.session_state.past_results)
    if not suggestion:
        st.info("Ne pas miser (aucune mise recommandée selon les règles / bankroll).")
    else:
        df_sugg = pd.DataFrame([
            {"section": k, "mise($)": round(v,2)} for k,v in suggestion.items()
        ]).sort_values("section")
        st.table(df_sugg)

# -----------------------
# Si un bouton a été cliqué -> appliquer le spin
# -----------------------
if 'spin_input' in locals() and spin_input:
    # on charge suggestion au moment du spin
    current_sugg = bot.suggest_bet(st.session_state.past_results)
    # Affiche la suggestion qui a été utilisée
    st.markdown("### Suggestion utilisée pour ce spin")
    if current_sugg:
        st.table(pd.DataFrame([{"section":k,"mise($)":round(v,2)} for k,v in current_sugg.items()]))
    else:
        st.info("Aucune mise (bot a recommandé de ne pas parier).")

    # Appliquer le spin (met à jour bankroll, history)
    result = bot.apply_spin(spin_input, current_sugg)
    st.write(f"**Résultat du spin :** {spin_input} — **{result['outcome']}**")
    if result["outcome"] == "HIT":
        st.success(f"Gagné: {result['win_amount']:.2f}$")
    else:
        st.error(f"Perdu: {result['total_bet']:.2f}$")

    # append history
    st.session_state.history_df = pd.concat([
        st.session_state.history_df,
        pd.DataFrame([{
            "timestamp": result["timestamp"],
            "spin": result["spin"],
            "total_bet": result["total_bet"],
            "win_amount": result["win_amount"],
            "bankroll_before": result["bankroll_before"],
            "bankroll_after": result["bankroll_after"],
            "outcome": result["outcome"]
        }])
    ], ignore_index=True)

    # append to past_results
    st.session_state.past_results.append(spin_input)

    # redraw (no rerun), show bankroll
    st.experimental_rerun()

# -----------------------
# HISTORIQUE & EXPORTS
# -----------------------
st.markdown("---")
st.subheader("Historique des spins")
st.write(f"Total spins enregistrés : {len(st.session_state.history_df)}")
st.dataframe(st.session_state.history_df.tail(20), use_container_width=True)

# Equity chart (matplotlib)
if len(st.session_state.history_df) > 0:
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(st.session_state.history_df["bankroll_after"].astype(float).values)
    ax.set_title("Courbe d'équité (bankroll after chaque spin)")
    ax.set_xlabel("Index spin")
    ax.set_ylabel("Bankroll ($)")
    ax.grid(True)
    st.pyplot(fig)

# Export CSV
if not st.session_state.history_df.empty:
    csv = st.session_state.history_df.to_csv(index=False).encode('utf-8')
    st.download_button("Télécharger l'historique CSV", data=csv, file_name="crazytime_history.csv", mime="text/csv")

st.markdown("---")
st.caption("⚠️ Ce logiciel fournit des suggestions — ne place pas de mises automatiques sur un casino sans vérifier les règles et la législation locale. Utilise uniquement à des fins d'analyse / simulation.")
