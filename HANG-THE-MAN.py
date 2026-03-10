from flask import Flask, render_template
import threading
import mysql.connector
import tkinter as tk
from tkinter import messagebox, simpledialog
import random
import winsound
import bcrypt
import webbrowser
import os
import sys

#----------------- HELPER FUNCTION --------------------

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def play_sound(filename, loop=False):
    flags = winsound.SND_FILENAME | winsound.SND_ASYNC
    
    if loop:
        flags |= winsound.SND_LOOP

    winsound.PlaySound(
        resource_path(f"sounds/{filename}"),
        flags
    )

# ------------------ DATABASE SETUP ------------------

def get_connection():
    return mysql.connector.connect(
        host="yamabiko.proxy.rlwy.net",
        user="root",
        password="stfCkRokiENKuGsGETBakdrBITjPBXGz",
        database="railway",
        port=44383
    )

#-------------------PASSWORD HASHING--------------------

def hash_pass(password):
    return bcrypt.hashpw(password.encode(),  bcrypt.gensalt()).decode() 

def verify_password(password, stored_hash):
    return bcrypt.checkpw(password.encode(), stored_hash.encode())

# ------------------ DATABASE FUNCTION ------------------

def db(difficulty):
    con = get_connection()
    cursor = con.cursor()

    query = """
        SELECT word_id, word, hint
        FROM words
        WHERE difficulty = %s
        ORDER BY RAND()
        LIMIT 1
    """

    cursor.execute(query, (difficulty.upper(),))
    row = cursor.fetchone()

    if not row:
        con.close()
        raise ValueError(f"No words found for difficulty: {difficulty}")

    word_id, word, hint = row

    con.close()
    return word, hint

# ------------------ MULTIPLAYER ROOM ------------------

def join_or_create_room(player_id):
    con = get_connection()
    cursor = con.cursor()

    cursor.execute("""
        SELECT r.room_id, r.word_id
        FROM rooms r
        JOIN room_players rp ON r.room_id = rp.room_id
        WHERE rp.player_id = %s
        AND r.status = 'waiting'
        LIMIT 1
    """, (player_id,))

    existing_room = cursor.fetchone()

    if existing_room:
        con.close()
        return existing_room

    # look for waiting room
    cursor.execute("""
        SELECT room_id, word_id
        FROM rooms
        WHERE status = 'waiting' AND player_count < 4
        ORDER BY created_at ASC    
        LIMIT 1
    """)

    room = cursor.fetchone()

    if room:
        room_id, word_id = room

        cursor.execute("""
            SELECT id FROM room_players
            WHERE room_id = %s AND player_id = %s
        """, (room_id, player_id))

        already_joined = cursor.fetchone()

        if not already_joined:
            cursor.execute("""
                INSERT INTO room_players (room_id, player_id)
                VALUES (%s, %s)
            """, (room_id, player_id))

            cursor.execute("""
                UPDATE rooms
                SET player_count = player_count + 1
                WHERE room_id = %s
            """, (room_id,))

        con.commit()
        con.close()
        return room_id, word_id

    else:
        # choose random word
        cursor.execute("""
            SELECT word_id FROM words
            ORDER BY RAND()
            LIMIT 1
        """)
        word_id = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO rooms (word_id, status, player_count)
            VALUES (%s, 'waiting', 1)
        """, (word_id,))

        room_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO room_players (room_id, player_id)
            VALUES (%s, %s)
        """, (room_id, player_id))

        con.commit()
        con.close()

        return room_id, word_id

# ------------------ GAME FUNCTION ------------------

player_id = None
player_name = ""
first_time = True

def start_game(difficulty=None, word=None, hint=None, multiplayer= False, room_id=None):
    #winsound.PlaySound(None, winsound.SND_PURGE)
    global ch, inds, Word, k, first_time

    if word is None:
        ch, hint = db(difficulty)
    else:
        ch = word
    inds = []
    Word = list("_" * len(ch))
    k = 5

    time_left = 120
    timer_running = True

    game_win=tk.Toplevel(root)
    game_win.title("GAME!!")
    game_win.geometry("2000x2000")
    game_win.config(bg="#E6DFDD")

    if first_time:
        def show_reward_popup():
            messagebox.showinfo(
                " --🪿-- ",
                "You'll be rewarded with 10 coins for each right answer."
            )

        game_win.after(100, show_reward_popup)
        first_time = False

    hframe= tk.Frame(game_win)
    hframe.pack(pady=(10,5))

    tk.Label(
        hframe,
        text="Hang-The-Man",
        font=("Chiller", 40, "bold", "underline"),
        fg="darkred"
        ).pack()

    top_info_frame= tk.Frame(
        game_win,
        bg="#F0EAE4",
        highlightthickness=2,
        highlightbackground="black",
        highlightcolor="black",
        padx=20,
        pady=12)
    top_info_frame.pack(pady=(5, 10))

    # -------- Fetch coins and cues from DB --------
    con = get_connection()
    cursor = con.cursor()

    cursor.execute(
        "SELECT total_score, cues_left FROM scores WHERE player_id = %s",
        (player_id,)
    )

    result = cursor.fetchone()
    con.close()

    if result:
        coins, cues_left = result
    else:
        coins, cues_left = 0, 0


    def use_cue():
        con = get_connection()
        cursor = con.cursor()

        cursor.execute(
            "SELECT total_score, cues_left FROM scores WHERE player_id = %s",
            (player_id,)
        )

        coins, cues = cursor.fetchone()

        # -------- CASE 1: Player already has cue --------
        if cues > 0:

            cursor.execute(
                "UPDATE scores SET cues_left = cues_left - 1 WHERE player_id = %s",
                (player_id,)
            )

            cues -= 1
            cuebtn.config(text=f"🎯CUE: {cues}")

            # Reveal letter
            hidden_indices = [i for i, letter in enumerate(Word) if letter == "_"]

            if hidden_indices:
                reveal_index = random.choice(hidden_indices)
                Word[reveal_index] = ch[reveal_index]
                wd.set(" ".join(Word))
                play_sound("right_letter.wav")

            con.commit()
            con.close()
            return

        # -------- CASE 2: cues == 0 --------
        else:

            if coins < 5:
                messagebox.showerror(
                    "💀 Broke Alert",
                    "You tried to buy wisdom with 0 money?\nEven the hangman feels bad."
                )
                con.close()
                return

            # Ask confirmation
            buy = messagebox.askyesno(
                "Deal With The Devil?",
                "Spend 5 shiny coins for one tiny hint?\n(No refunds. No mercy.)"
            )

            if not buy:
                con.close()
                return

            # Deduct coins and add 1 cue
            cursor.execute(
                """
                UPDATE scores
                SET total_score = total_score - 5,
                    cues_left = cues_left + 1
                WHERE player_id = %s
                """,
                (player_id,)
            )

            coins -= 5
            cues += 1

            coin_label.config(text=f"🪙Coins: {coins}")
            cuebtn.config(text=f"🎯CUE: {cues}")

            con.commit()
            con.close()

            messagebox.showinfo(
                "💸 Transaction Successful",
                "5 coins vanished into thin air.\nClick again to use it wisely."
            )

            return
        
    if not multiplayer:
        cuebtn = tk.Button(
            top_info_frame,
            text=f"🎯CUE: {cues_left}",
            font=("Comic Sans MS", 14),
            cursor="hand2",
            command=lambda:(play_sound("click.wav"), use_cue())
        )
        cuebtn.pack(side="left", padx=80)

    timer_label = tk.Label(
        top_info_frame, 
        text=f"⏱Time Left: {time_left}s",
        font=("Comic Sans MS",  15, "bold"),
        fg="darkgreen"
    )
    timer_label.pack(side="left", padx=80)

    coin_label = tk.Button(
        top_info_frame, 
        text=f"🪙Coins: {coins}",   
        font=("Comic Sans MS", 14),
        cursor="hand2",
        command=lambda: (play_sound("click.wav"),top_info_frame.after(200, lambda: [messagebox.showinfo(
            "🪙 Coin Rules",
            "Crack the word and collect 10 coins.\n"
            "(Coins = Score, Earn some more or hit the floor.)"
        )]))
    )
    coin_label.pack(side="left", padx=80)

    images = [
        tk.PhotoImage(file=resource_path("stage0.png")),
        tk.PhotoImage(file=resource_path("stage1.png")),
        tk.PhotoImage(file=resource_path("stage2.png")),
        tk.PhotoImage(file=resource_path("stage4.png")),
        tk.PhotoImage(file=resource_path("stage5.png")),
        tk.PhotoImage(file=resource_path("stage7.png"))
    ]

    taglines = [
        "\nThe stage is set…\nLet's test your survival instincts.",
        "\nUh-oh Heads Up!!",
        "\nSomeone's a little stiff,\nKeep guessing!",
        "\nSwinging into trouble,\nare we?",
        "\nTryna reach out?\nSad, cause no one's gonna help",
        "\nOops! seems like you're dead.\n(for good)"
    ]

    main_frame = tk.Frame(
        game_win,
        bg="#F2ECE6",
        highlightthickness=5,
        highlightbackground="black",
        highlightcolor="black",        #window focuses on screen so that the border color doesn't change after popup
        padx=30,
        pady=15)
    main_frame.pack(padx=60,pady=(10,5))

    left_frame = tk.Frame(
        main_frame,
        width=500,
        height=450,
        bg="#ffd6dc",
        highlightthickness=5,
        highlightbackground="#c08090",
        padx=20,
        pady=20)
    left_frame.pack(side="left",expand=True, padx=40, pady=20)
    left_frame.pack_propagate(False)       #used so that the size of the frame doesn't depend on it's components and is fixed width and height is mandatory when it's used  

    photo_label = tk.Label(
    left_frame,
    text=taglines[0],
    font=("Chiller", 18, "italic"),
    bg="pink",
    compound="top",
    image=images[0]
    )

    photo_label.image = images[0]
    photo_label.pack(expand= True, fill= "both")
    
    right_frame= tk.Frame(
        main_frame,
        width=500,
        height=450,
        bg="lightblue",
        highlightthickness=5,
        highlightbackground="#7A9DB6",
        highlightcolor="#7A9DB6",
        padx=20,
        pady=20
        )
    right_frame.pack(side="left", expand=True, padx=40, pady=20)
    right_frame.pack_propagate(False)
    
    hl = tk.Label( 
        right_frame, 
        text=f"Hint: {hint}",
        font=("Comic Sans MS", 12)
    )
    hl.pack(pady=(10,20))
    
    wd = tk.StringVar()
    wd.set(" ".join(Word))

    wl = tk.Label(right_frame, textvariable=wd, font=("Helevetica", 18))
    wl.pack(pady=(10,25))

    entry = tk.Entry(right_frame, font=("Courier", 16), takefocus=True)
    entry.pack(pady=(5,20))
    entry.focus_set()
    game_win.after(100, lambda: entry.focus_force())

    wgl = tk.Label( 
        right_frame, 
        text=f"Wrong Attempts Left: {k}",
        font=("Comic Sans MS", 12),
        fg="darkred"
    )
    wgl.pack(pady=(10,15))

    ml = tk.Label( 
        right_frame, 
        text="",
        font=("Comic Sans MS", 12),
        fg="darkblue"
    )
    ml.pack(pady=(10,25)) 

    fframe=tk.Frame(game_win)
    fframe.pack(pady=(2, 10))

    tk.Label(
        fframe,
        text="💡 Tip: Press Esc anytime to leave the game",
        font=("Comic Sans MS", 11, "italic"),
        fg="#555555",
        bg="#E6DFDD"
    ).pack(padx=10, pady=5)

    
    def play():
        nonlocal timer_running
        global k, Word, ch, inds

        letter = entry.get().lower()
        entry.delete(0, tk.END)

        if len(letter) != 1:
            ml.config(text="Enter a single alphabet!")
            return

        if letter in inds:
            ml.config(text="You already guessed that!")
            return

        if letter in ch:
            play_sound("right_letter.wav")
            inds.append(letter)
            ml.config(text="CORRECT!")
            for i in range(len(ch)):
                if ch[i] == letter:
                    Word[i] = letter
        else:
            play_sound("wrong_letter.wav")
            k -= 1
            photo_label.config(
                text=taglines[5 - k],
                image=images[5 - k]
            )
            photo_label.image = images[5 - k]
            ml.config(text="Try again")
            wgl.config(text=f"Wrong Attempts Left: {k}")

        wd.set(" ".join(Word))

        if "_" not in Word:
            play_sound("game_won.wav")
            timer_running = False
            ml.config(text="Congrats!! You won")
            entry.config(state="disabled")
            btn.config(state="disabled")

            if multiplayer:
                winner = multiplayer_winner(room_id)
                if winner:
                    name, time_taken, wrong = winner
                    messagebox.showinfo(
                        "Winner",
                        f"{name} escaped the noose!\n"
                        f"Time: {time_taken}s\n"
                        f"Wrong attempts: {wrong}"
                    )
                
            con = get_connection()
            cursor = con.cursor()

            cursor.execute(
                """
                UPDATE scores
                SET total_score = total_score + 10,
                    games_played = games_played + 1,
                    games_won = games_won + 1
                WHERE player_id = %s
                """,
                (player_id,)
            )

            con.commit()

            cursor.execute(
                """
                SELECT total_score
                FROM scores
                WHERE player_id = %s
                """,
                (player_id,)
            )
            new_coins = cursor.fetchone()[0]
            coin_label.config(text=f"🪙Coins: {new_coins}")
            con.close()

            if multiplayer:
                con = get_connection()
                cursor = con.cursor()

                cursor.execute("""
                    UPDATE room_players
                    SET solved = 1,
                        wrong_attempts = %s,
                        finished_at = NOW(),
                        time_taken = %s
                    WHERE room_id = %s AND player_id = %s
                """, (5 - k, 120 - time_left, room_id, player_id))

                con.commit()
                con.close()

            askuser()

        elif k == 0:
            play_sound("game_lose.wav")
            timer_running = False
            ml.config(text=f"Game Over! Word was: {ch.upper()}")
            entry.config(state="disabled")
            btn.config(state="disabled")

            con = get_connection()
            cursor = con.cursor()

            cursor.execute(
                """
                UPDATE scores
                SET games_played = games_played + 1
                WHERE player_id = %s
                """,
                (player_id,)
            )
            con.commit()
            con.close()

            if multiplayer:
                con = get_connection()
                cursor = con.cursor()

                cursor.execute("""
                    UPDATE room_players
                    SET solved = 0,
                        wrong_attempts = %s,
                        finished_at = NOW(),
                        time_taken = %s
                    WHERE room_id = %s AND player_id = %s
                """, (5, 120 - time_left, room_id, player_id))

                con.commit()
                con.close()
            askuser()
       
    btn = tk.Button(
        right_frame,
        text="Submit",
        command= lambda:(play_sound("click.wav"),play()),
        font=("Helevetica", 14, "bold"),
        bg="lavender",
        cursor="hand2"
    )
    btn.pack(pady=(15,10))
    
    game_win.bind("<Return>", lambda event: (play_sound("click.wav"),play()))

    def on_escape(event=None):
        play_sound("click.wav")
        if messagebox.askyesno(
            "Exit Game",
            "Do you want to quit the current game?"
        ):
            game_win.destroy()
            open_menu()
            game_win.after(150, lambda: entry.focus_force())

    game_win.bind("<Escape>", on_escape)

    def countdown():
        nonlocal time_left, timer_running

        if not timer_running:
            return

        if time_left > 0:
            time_left -= 1
            timer_label.config(text=f"Time Left: {time_left}s")
            game_win.after(1000, countdown)
        else:
            timer_running = False
            if "_" in Word:
                play_sound("game_won.wav")
                messagebox.showinfo(
                    "⏰ Time’s up!",
                    "OOPSS! The rope didn’t wait and neither did the clock 👻"
                )
                entry.config(state="disabled")
                btn.config(state="disabled")
                askuser()
                game_win.after(150, lambda: entry.focus_force())

    def askuser():
        response = messagebox.askyesno(
            "Enjoyed Playing?",
            "Would you like to continue?"
        )
        if response:
            game_win.destroy()
            start_game(difficulty)
        else:
            game_win.destroy()
            open_menu()

    game_win.after(1000, countdown)

# ------------------ MULTIPLAYER LOBBY ------------------

def start_multiplayer_game(word_id, room_id):

    con = get_connection()
    cursor = con.cursor()

    cursor.execute(
        "SELECT word, hint FROM words WHERE word_id = %s",
        (word_id,)
    )

    word, hint = cursor.fetchone()
    con.close()

    start_game(word=word, hint=hint, multiplayer=True, room_id=room_id)

def open_lobby(room_id, word_id):

    lobby = tk.Toplevel(root)
    lobby.title("Multiplayer Lobby")
    lobby.geometry("2000x2000")
    lobby.config(bg="black")

    photo = tk.PhotoImage(file=resource_path("hanged.png"))

    tk.Label(
        lobby,
        image=photo,
        text="GAME LOBBY \nPlayers Incoming ",
        font=("Chiller", 22, "bold"),
        bg="#18181A",
        fg="white",
        compound="top"
    ).pack(pady=5)

    tk.Label.image = photo

    timer_label = tk.Label(lobby, text="Game starts in: 20 sec..", font=("Arial", 18), fg = "black")
    timer_label.pack(pady=20)

    players_label = tk.Label(lobby, text="Players:", font=("Arial", 14), fg = "black")
    players_label.pack(pady=10)

    players_list = tk.Label(lobby, text="", font=("Arial", 12), fg = "black")
    players_list.pack()

    time_left = 20
    db_check_counter = 0
    player_count=0
    status="waiting"

    def countdown():
        nonlocal time_left, db_check_counter, player_count, status
        db_check_counter += 1

        if db_check_counter % 5 == 0:
            players_list.pack()
            con = get_connection()
            cursor = con.cursor()
            cursor.execute("""
                SELECT player_count, status
                FROM rooms
                WHERE room_id = %s
            """, (room_id,))
            
            player_count, status = cursor.fetchone()
            players_label.config(text=f"Players: {player_count}")
            
            cursor.execute("""
                SELECT p.username
                FROM room_players rp
                JOIN players p ON rp.player_id = p.player_id
                WHERE rp.room_id = %s
                """, (room_id,))
            
            players = cursor.fetchall()
            player_names = "\n".join([p[0] for p in players])
            
            players_list.config(text=player_names)
            con.close()
            

        # If room fills completely
        if player_count >= 4:

            con = get_connection()
            cursor = con.cursor()
            cursor.execute("""
                UPDATE rooms
                SET status = 'started', start_time = NOW()
                WHERE room_id = %s
            """, (room_id,))

            con.commit()
            con.close()
            
            start_multiplayer_game(word_id, room_id)
            lobby.destroy()
            return

        # If timer ends
        if time_left <= 0:
            if player_count >= 2:
                con = get_connection()
                cursor = con.cursor()
                cursor.execute("""
                    UPDATE rooms
                    SET status = 'started', start_time = NOW()
                    WHERE room_id = %s
                """, (room_id,))
                con.commit()
                con.close()
                start_multiplayer_game(word_id, room_id)
                lobby.destroy()
                
            else:
                con = get_connection()
                cursor = con.cursor()
                cursor.execute("""
                    UPDATE rooms
                    SET status = 'expired'
                    WHERE room_id = %s
                """, (room_id,))
                con.commit()
                con.close()
                lobby.destroy()
                messagebox.showinfo(
                    "No Players Found",
                    "Even the ghosts refused to play.\nTry multiplayer again."
                )
                lobby.destroy()
                game_mode()
            return

        time_left -= 1
        timer_label.config(text=f"Game starts in: {time_left}")

        lobby.after(1000, countdown)

    countdown()
    

# ------------------ FLASK FUNCTION ------------------

app = Flask(__name__)

@app.route("/leaderboard")
def leaderboard():
    con = get_connection()
    cursor = con.cursor()
    
    cursor.execute(
        """
        SELECT p.username, s.total_score
        FROM players p
        JOIN scores s ON p.player_id = s.player_id
        ORDER BY s.total_score DESC
        """
    )
    
    players = cursor.fetchall()
    con.close()
    
    return render_template("leaderboard.html", players=players)

def run_flask():
    app.run(debug=False)

#--------------------Multiplayer Winner-------------
def multiplayer_winner(room_id):

    con = get_connection()
    cursor = con.cursor()

    cursor.execute("""
        SELECT p.username, rp.time_taken, rp.wrong_attempts
        FROM room_players rp
        JOIN players p ON rp.player_id = p.player_id
        WHERE rp.room_id = %s
        AND rp.solved = 1
        ORDER BY rp.time_taken ASC,
                 rp.wrong_attempts ASC,
                 rp.finished_at ASC
        LIMIT 1
    """, (room_id,))

    winner = cursor.fetchone()

    con.close()

    return winner

# ------------------ MENU FUNCTION ------------------

def open_menu():
    play_sound("strangerthings_theme.wav", loop=True)
    menu = tk.Toplevel(root)
    menu.title("Menu")
    menu.geometry("2000x2000")
    menu.config(bg="#18181A")

    tk.Label(
        menu,
        text="WELCOME TO HANGMAN",
        font=("Chiller", 40, "bold underline"),
        bg="pink",
        fg="black"
    ).pack(pady=15)

    photo = tk.PhotoImage(file=resource_path("hanged.png"))

    tk.Label(
        menu,
        image=photo,
        text="""👻   Guess it right or face the fight,
With wit and words, you’ll win the night.
One mistake is fine, the fifth’s your doom,
So choose with care, or meet your gloom! 👻""",
        font=("Comic Sans MS", 12, "italic"),
        bg="#18181A",
        fg="white",
        compound="top"
    ).pack(pady=5)

    tk.Label.image = photo

    tk.Button(
        menu,
        text="  ▶ Play",
        command= lambda: [menu.destroy(), play_choice()],
        font=("Chiller", 20, "bold"),
        bg="pink",
        cursor="hand2",
        width=20
    ).pack(pady=5)

    tk.Button(
        menu,
        text="  📖 Rules",
        command= lambda: [webbrowser.open(resource_path("hangman html/rules.html"))],
        font=("Chiller", 20, "bold"),
        bg="pink",
        cursor="hand2",
        width=20
    ).pack(pady=5)

    tk.Button(
        menu,
        text="  🏆 Scores",
        command= lambda: [webbrowser.open("http://127.0.0.1:5000/leaderboard")],
        font=("Chiller", 20, "bold"),
        bg="pink",
        cursor="hand2",
        width=20
    ).pack(pady=5)

    tk.Button(
        menu,
        text="  ℹ About",
        command=lambda: [webbrowser.open(resource_path("hangman html/about.html"))],
        font=("Chiller", 20, "bold"),
        bg="pink",
        cursor="hand2",
        width=20
    ).pack(pady=5)

    tk.Button(
        menu,
        text="  ❌ Exit",
        command= lambda: [messagebox.askyesno(
            "Exit",
            "Are you sure you wanna exit?"
        ) and menu.destroy()],
        width=20,
        font=("Chiller", 20, "bold"),
        bg="pink",
        cursor="hand2"
    ).pack(pady=5)

# ------------------ PLAY CHOICE FUNCTION ------------------

def play_choice():
    choice_win = tk.Toplevel(root)
    choice_win.title("Play Hangman")
    choice_win.geometry("2000x2000")
    choice_win.config(bg="#18181A")
    
    tk.Label(
        choice_win,
        text="Choose an option",
        bg="pink",
        fg="black",
        font=("Chiller", 40, "bold")
    ).pack(pady=30)

    photo = tk.PhotoImage(file=resource_path("hanged.png"))

    tk.Label(
        choice_win,
        image=photo,
        text="""👻   Guess it right or face the fight,
With wit and words, you’ll win the night.
One mistake is fine, the fifth’s your doom,
So choose with care, or meet your gloom! 👻""",
        font=("Comic Sans MS", 12, "italic"),
        bg="#18181A",
        fg="white",
        compound="top"
    ).pack(pady=5)

    tk.Label.image = photo

    tk.Button(
        choice_win,
        text="Login",
        font=("Helevetica", 16, "bold"),
        bg="pink",
        fg="black",
        cursor="hand2",
        width=20,
        command= lambda: [choice_win.destroy(), login_user()]
    ).pack(pady=(20,15))

    tk.Button(
        choice_win,
        text="Signup",
        font=("Helevetica", 16, "bold"),
        bg="pink",
        fg="black",
        cursor="hand2",
        width=20,
        command= lambda: [choice_win.destroy(), signup_user()]
    ).pack(pady=15)

# ------------------ LOGIN FUNCTION ------------------
def login_user():
    login_win = tk.Toplevel(root)
    login_win.title("Login")
    login_win.geometry("2000x2000")
    login_win.config(bg="#18181A")

    photo = tk.PhotoImage(file=resource_path("hanged.png"))

    tk.Label(
        login_win,
        image=photo,
        text="""👻   Guess it right or face the fight,
With wit and words, you’ll win the night.
One mistake is fine, the fifth’s your doom,
So choose with care, or meet your gloom! 👻""",
        font=("Chiller", 12, "italic"),
        bg="#18181A",
        fg="white",
        compound="top"
    ).pack(pady=5)

    tk.Label.image = photo
    
    tk.Label(
        login_win,
        text="Username/Email",
        bg="pink",
        fg="black",
        font=("Comic Sans MS", 16)
    ).pack(pady=(10,10))

    username_entry = tk.Entry(login_win, font=("Courier", 16),bg="pink",fg="black")
    username_entry.pack(pady=10)

    tk.Label(
        login_win,
        text="Password",
        bg="pink",
        fg="black",
        font=("Comic Sans MS", 16)
    ).pack(pady=10)

    password_entry = tk.Entry(
        login_win,
        font=("Courier", 16),
        bg="pink",
        fg="black",
        show="*"
    )
    password_entry.pack(pady=10)

    def forgot_password():
        email = simpledialog.askstring(
            "Reset Password",
            "Enter your registered mail: "
        )
        if not email:
            return
        new_password = simpledialog.askstring(
            "New Password",
            "Enter new password: ",
            show="*"
        )
        if not new_password:
            return

        con = get_connection()
        cursor = con.cursor()
        cursor.execute(
            "UPDATE players SET password_hash = %s WHERE email = %s",
            (hash_pass(new_password), email)
        )
        if cursor.rowcount == 0:
            messagebox.showerror("Error","Email not found!")
        else:
            con.commit()
            messagebox.showinfo("Success","Password reset successfully!")
        con.close()

    def submit_login():
        global player_id, player_name
        
        user_input = username_entry.get().strip()
        password = password_entry.get().strip()



        loading_label = tk.Label(
        login_win,
        text="Loading...\nHang tight while we prepare the game ⏳",
        font=("Comic Sans MS", 14, "bold"),
        fg="darkred",
        wraplength=320,
        justify="center",
        )
        loading_label.pack(pady=10)

        login_win.update()

        con = get_connection()
        cursor = con.cursor()

        cursor.execute(
            """
            SELECT player_id, username, password_hash
            FROM players
            WHERE username=%s OR email=%s
            """,
            (user_input, user_input)
        )

        result = cursor.fetchone()

        if result:
            player_id, username, stored_password = result

            # Check password
            if verify_password(password, stored_password):
                player_name = username  # store username properly

                messagebox.showinfo(
                    "Success",
                    f"Welcome back {username}!"
                )

                login_win.destroy()
                game_mode()
            else:
                messagebox.showerror(
                    "Error",
                    "Incorrect password!"
                )

        else:
            if messagebox.askyesno(
                "Not Found",
                "User not found. Do you want to signup?"
            ):
                login_win.destroy()
                signup_user()

        con.close()

    tk.Button(
        login_win,
        text="Login",
        bg="pink",
        fg="black",
        font=("Chiller", 18, "bold"),
        cursor="hand2",
        command= submit_login
    ).pack(pady=30)

    tk.Button(
        login_win,
        text="Forgot Passsword?",
        font=("Comic Sans MS", 15, "italic"),
        bg="red",
        fg="black",
        cursor="hand2",
        command= forgot_password
    ).pack(pady=50)

# ------------------ SIGNUP FUNCTION ------------------

def signup_user():
    signup_win = tk.Toplevel(root)
    signup_win.title("Signup")
    signup_win.geometry("2000x2000")
    signup_win.config(bg="#18181A")

    tk.Label(signup_win, text="Email", font=("Comic Sans MS", 14),bg="pink",fg="black").pack(pady=10)
    email_entry = tk.Entry(signup_win, font=("Courier", 14),bg="pink",fg="black")
    email_entry.pack(pady=10)

    tk.Label(signup_win, text="First Name", font=("Comic Sans MS", 14),bg="pink",fg="black").pack(pady=10)
    first_name_entry = tk.Entry(signup_win, font=("Courier", 14),bg="pink",fg="black")
    first_name_entry.pack(pady=10)

    tk.Label(signup_win, text="Last Name", font=("Comic Sans MS", 14),bg="pink",fg="black").pack(pady=10)
    last_name_entry = tk.Entry(signup_win, font=("Courier", 14),bg="pink",fg="black")
    last_name_entry.pack(pady=10)

    tk.Label(signup_win, text="Phone Number (Optional)", font=("Comic Sans MS", 14),bg="pink",fg="black").pack(pady=10)
    phone_entry = tk.Entry(signup_win, font=("Courier", 14),bg="pink",fg="black")
    phone_entry.pack(pady=10)

    tk.Label(signup_win, text="Create a username", font=("Comic Sans MS", 14),bg="pink",fg="black").pack(pady=10)
    username_entry = tk.Entry(signup_win, font=("Courier", 14),bg="pink",fg="black")
    username_entry.pack(pady=10)

    tk.Label(signup_win, text="Create a password", font=("Comic Sans MS", 14),bg="pink",fg="black").pack(pady=10)
    password_entry = tk.Entry(signup_win, font=("Courier", 14),bg="pink",fg="black", show="*")
    password_entry.pack(pady=10)

    def submit_signup():
        global player_id, player_name

        email = email_entry.get().strip()
        first_name = first_name_entry.get().strip()
        last_name = last_name_entry.get().strip()
        phone = phone_entry.get().strip()
        username = username_entry.get().strip()
        password = password_entry.get().strip()

        if not email or not username or not password or not first_name or not last_name:
            messagebox.showwarning(
                "Warning",
                "All fields except phone are required!"
            )
            return

        if not email.endswith("@gmail.com"):
            messagebox.showerror(
                "Error",
                "Invalid Email!"
            )
            return

        if phone:
            if not phone.isdigit() or len(phone)!= 10:
                messagebox.showerror(
                    "Error",
                    "Invalid Phone Number!"
                )
                return
        
        con = get_connection()
        cursor = con.cursor()

        try:
        # Insert into Players table
            hashed_password = hash_pass(password)
            cursor.execute(
                """
                INSERT INTO players
                (username, email, password_hash, first_name, last_name, phone)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (username, email, hashed_password, first_name, last_name, phone)
            )

        # Get the auto generated player_id
            player_id = cursor.lastrowid
            player_name = username

            # Insert into Scores table
            cursor.execute(
                """
                INSERT INTO scores
                (player_id, total_score, games_played, games_won, cues_left)
                VALUES (%s, 0, 0, 0, 3)
                """,
                (player_id,)
            )

            con.commit()

            messagebox.showinfo("Success", "Signup successful!")
            signup_win.destroy()
            game_mode()

        except mysql.connector.IntegrityError:
            messagebox.showerror(
                "Error",
                "Email or Username already exists!"
            )

        finally:
            con.close()

    tk.Button(
        signup_win,
        text="Signup",
        font=("Helevetica", 16, "bold"),
        bg="pink",
        fg="black",
        cursor="hand2",
        command= submit_signup
    ).pack(pady=20)

#-------------------GAME MODE----------------------
def game_mode():
    mode_win = tk.Toplevel(root)
    mode_win.title("GAME MODE")
    mode_win.geometry("2000x2000")
    mode_win.config(bg="#18181A")

    # ---------- Dropdown ----------
    dropdown_var = tk.StringVar()
    dropdown_var.set("Select Difficulty")

    dropdown = tk.OptionMenu(
        mode_win,
        dropdown_var,
        "Easy", "Medium", "Hard"
    )

    dropdown.config(
        font=("Comic Sans MS", 14),
        bg="pink",
        fg="black",
        width=15
    )

    dropdown["menu"].config(
    bg="pink",
    fg="black",
    font=("Comic Sans MS", 12)
    )

    dropdown.pack_forget()   # ✅ actually hide it

    # ---------- Start button ----------
    start_btn = tk.Button(
        mode_win,
        text="Start Game",
        font=("Helevetica", 14, "bold"),
        bg="lightgreen",
        cursor="hand2",
        command=lambda:
            (winsound.PlaySound(None, winsound.SND_PURGE),
             play_sound("click.wav"),
             start_single_player(mode_win, dropdown_var))
    )

    start_btn.pack_forget()  # hidden initially

    # ---------- Functions ----------
    def sp_opt():
        dropdown.pack(pady=20)
        start_btn.pack(pady=15)

    def start_single_player(mode_win, dropdown_var):
        difficulty = dropdown_var.get()

        if difficulty == "Select Difficulty":
            messagebox.showwarning(
                "Select Difficulty",
                "Please choose a difficulty level"
            )
            return

        start_btn.config(state="disabled")

        loading_label = tk.Label(
            mode_win,
            text="The database is yawning,\ngive it a second⏳",
            font=("Comic Sans MS", 16, "bold"),
            fg="darkblue"
        )
        loading_label.pack(pady=20)

        mode_win.update()  # force UI refresh

        start_game(difficulty)
        mode_win.destroy()

    def start_multiplayer(mode_win):
        tk.Label(
            mode_win,
            text="Summoning other players...\nDon't You Dare Blink",
            font=("Comic Sans MS", 14)
        ).pack(pady=20)

        mode_win.update()

        room_id, word_id = join_or_create_room(player_id)
        open_lobby(room_id, word_id)
        mode_win.destroy()

    # ---------- UI ----------
    tk.Label(
        mode_win,
        text="Choose Game Mode",
        font=("Chiller", 40, "bold"),
        fg="darkred"
    ).pack(pady=20)

    tk.Button(
        mode_win,
        text="Singleplayer",
        font=("Helevetica", 14),
        bg="pink",
        fg="black",
        cursor="hand2",
        command= sp_opt
    ).pack(pady=(40, 10))

    mp_button = tk.Button(
        mode_win,
        text="Multiplayer",
        font=("Helevetica", 14),
        bg="pink",
        fg="black",
        cursor="hand2",
        command=lambda: [mp_button.config(state="disabled"), start_multiplayer(mode_win)]
    )
    mp_button.pack(pady=(40, 40))
# ------------------ RUN PROGRAM ------------------

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    root=tk.Tk()
    root.withdraw()
    open_menu()
    root.mainloop()


