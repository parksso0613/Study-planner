import streamlit as st
import sqlite3
import hashlib
import datetime
import pandas as pd

st.set_page_config(
    page_title="스마트 스터디 플래너",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
    }
    .card {
        background-color: #F3F4F6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #3B82F6;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

DB_FILE = "study_planner.db"
SUPABASE_CONNECTED = False
supabase_client = None

if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
    try:
        from supabase import create_client
        supabase_url = st.secrets["SUPABASE_URL"]
        supabase_key = st.secrets["SUPABASE_KEY"]
        supabase_client = create_client(supabase_url, supabase_key)
        SUPABASE_CONNECTED = True
    except Exception as e:
        SUPABASE_CONNECTED = False

def get_sqlite_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not SUPABASE_CONNECTED:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                date TEXT NOT NULL,
                subject TEXT NOT NULL,
                task TEXT NOT NULL,
                study_minutes INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                priority TEXT DEFAULT '보통'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_memo (
                username TEXT NOT NULL,
                date TEXT NOT NULL,
                memo TEXT NOT NULL,
                PRIMARY KEY (username, date)
            )
        """)
        conn.commit()
        conn.close()

init_db()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed_password):
    return hash_password(password) == hashed_password

def create_user(username, password):
    hashed = hash_password(password)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if SUPABASE_CONNECTED:
        try:
            res = supabase_client.table("users").select("username").eq("username", username).execute()
            if res.data:
                return False
            supabase_client.table("users").insert({
                "username": username,
                "password": hashed,
                "created_at": now
            }).execute()
            return True
        except Exception:
            return False
    else:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password, created_at)", (username, hashed, now))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

def login_user(username, password):
    if SUPABASE_CONNECTED:
        try:
            res = supabase_client.table("users").select("password").eq("username", username).execute()
            if res.data and verify_password(password, res.data[0]["password"]):
                return True
            return False
        except Exception:
            return False
    else:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row and verify_password(password, row["password"]):
            return True
        return False

def add_task(username, date_str, subject, task, priority, minutes):
    if SUPABASE_CONNECTED:
        supabase_client.table("tasks").insert({
            "username": username,
            "date": date_str,
            "subject": subject,
            "task": task,
            "priority": priority,
            "study_minutes": minutes,
            "completed": False
        }).execute()
    else:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (username, date, subject, task, priority, study_minutes, completed) VALUES (?, ?, ?, ?, ?, ?, 0)",
            (username, date_str, subject, task, priority, minutes)
        )
        conn.commit()
        conn.close()

def get_tasks(username, date_str):
    if SUPABASE_CONNECTED:
        res = supabase_client.table("tasks").select("*").eq("username", username).eq("date", date_str).order("id", desc=True).execute()
        return res.data
    else:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE username = ? AND date = ? ORDER BY id DESC", (username, date_str))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

def update_task_status(task_id, completed):
    if SUPABASE_CONNECTED:
        supabase_client.table("tasks").update({"completed": completed}).eq("id", task_id).execute()
    else:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE tasks SET completed = ? WHERE id = ?", (1 if completed else 0, task_id))
        conn.commit()
        conn.close()

def delete_task(task_id):
    if SUPABASE_CONNECTED:
        supabase_client.table("tasks").delete().eq("id", task_id).execute()
    else:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()

def save_daily_memo(username, date_str, memo):
    if SUPABASE_CONNECTED:
        supabase_client.table("daily_memo").upsert({
            "username": username,
            "date": date_str,
            "memo": memo
        }).execute()
    else:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO daily_memo (username, date, memo) VALUES (?, ?, ?)",
            (username, date_str, memo)
        )
        conn.commit()
        conn.close()

def get_daily_memo(username, date_str):
    if SUPABASE_CONNECTED:
        res = supabase_client.table("daily_memo").select("memo").eq("username", username).eq("date", date_str).execute()
        return res.data[0]["memo"] if res.data else ""
    else:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT memo FROM daily_memo WHERE username = ? AND date = ?", (username, date_str))
        row = cursor.fetchone()
        conn.close()
        return row["memo"] if row else ""

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""

with st.sidebar:
    st.title("📚 Study Hub")
    
    if SUPABASE_CONNECTED:
        st.caption("🟢 **Supabase 클라우드 DB 연결됨** (데이터 영구 보존)")
    else:
        st.caption("🟡 **로컬 SQLite DB 모드** (Secrets 미설정)")
    
    if st.session_state["logged_in"]:
        st.success(f"**{st.session_state['username']}**님 환영합니다!")
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state["logged_in"] = False
            st.session_state["username"] = ""
            st.rerun()
    else:
        st.subheader("🔑 로그인 / 회원가입")
        auth_mode = st.radio("모드 선택", ["로그인", "회원가입"], key="auth_mode")
        
        input_user = st.text_input("아이디", key="auth_user")
        input_pass = st.text_input("비밀번호", type="password", key="auth_pass")
        
        if auth_mode == "로그인":
            if st.button("로그인", use_container_width=True, type="primary"):
                if login_user(input_user, input_pass):
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = input_user
                    st.success("로그인 성공!")
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
        else:
            if st.button("회원가입 완료", use_container_width=True, type="primary"):
                if input_user and input_pass:
                    if len(input_user) < 3:
                        st.warning("아이디는 3자 이상 입력해주세요.")
                    elif create_user(input_user, input_pass):
                        st.success("회원가입이 완료되었습니다! 로그인해주세요.")
                    else:
                        st.error("이미 존재하는 아이디입니다.")
                else:
                    st.warning("아이디와 비밀번호를 모두 입력해주세요.")

if not st.session_state["logged_in"]:
    st.markdown('<div class="main-header">📖 나만의 스마트 스터디 플래너</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">로그인하고 오늘의 공부 목표, 목표 시간, 달성률을 체계적으로 관리하세요.</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("🎯 **목표별 할 일 관리**\n\n과목별, 중요도별로 할 일을 정돈하고 완료 상태를 바로 체크해보세요.")
    with col2:
        st.success("⏱️ **공부 시간 트래킹**\n\n과목별로 투자한 공부 시간을 기록하고 통계로 확인할 수 있습니다.")
    with col3:
        st.warning("☁️ **클라우드 데이터 보존**\n\nSupabase 연동으로 새로고침 및 재부팅 후에도 완벽히 저장됩니다.")
    
    st.divider()
    st.caption("👈 좌측 사이드바에서 로그인 또는 회원가입을 먼저 진행해 주세요.")

else:
    st.markdown(f'<div class="main-header">📝 {st.session_state["username"]}님의 스터디 공간</div>', unsafe_allow_html=True)
    
    selected_date = st.date_input("📅 날짜 선택", datetime.date.today())
    date_str = selected_date.strftime("%Y-%m-%d")
    
    tab1, tab2, tab3 = st.tabs(["📋 일간 플래너", "📊 공부 통계", "💡 오늘의 피드백"])
    
    with tab1:
        st.subheader(f"{date_str} 학습 계획")
        
        with st.expander("➕ 새 학습 계획 추가하기", expanded=True):
            col_a, col_b, col_c, col_d = st.columns([2, 3, 2, 2])
            with col_a:
                subject = st.selectbox("과목", ["국어", "수학", "영어", "탐구", "코딩", "자격증", "기타"])
            with col_b:
                task_text = st.text_input("할 일 내용", placeholder="예: 수학 모의고사 1회 풀기")
            with col_c:
                priority = st.selectbox("중요도", ["높음 🔥", "보통 ⚡", "낮음 ☘️"])
            with col_d:
                study_min = st.number_input("목표 시간(분)", min_value=0, max_value=600, value=30, step=10)
            
            if st.button("플래너에 추가", type="primary"):
                if task_text.strip():
                    add_task(st.session_state["username"], date_str, subject, task_text, priority, study_min)
                    st.toast("계획이 추가되었습니다!", icon="✅")
                    st.rerun()
                else:
                    st.warning("할 일 내용을 입력해주세요.")
        
        tasks = get_tasks(st.session_state["username"], date_str)
        
        if not tasks:
            st.info("등록된 학습 계획이 없습니다. 위에서 새로운 목표를 추가해보세요!")
        else:
            completed_count = sum(1 for t in tasks if t["completed"])
            total_count = len(tasks)
            progress = completed_count / total_count if total_count > 0 else 0
            
            st.write(f"**오늘의 달성률:** {completed_count}/{total_count} ({int(progress * 100)}%)")
            st.progress(progress)
            st.divider()
            
            for task in tasks:
                t_id = task["id"]
                t_comp = bool(task["completed"])
                t_subj = task["subject"]
                t_text = task["task"]
                t_prio = task["priority"]
                t_min = task["study_minutes"]
                
                col_chk, col_info, col_del = st.columns([1, 8, 1])
                
                with col_chk:
                    is_done = st.checkbox("", value=t_comp, key=f"chk_{t_id}")
                    if is_done != t_comp:
                        update_task_status(t_id, is_done)
                        st.rerun()
                
                with col_info:
                    style = "text-decoration: line-through; color: #9CA3AF;" if is_done else "color: #1F2937;"
                    st.markdown(
                        f"<div style='font-size:1.05rem; {style}'>"
                        f"<b>[{t_subj}]</b> {t_text} <span style='font-size:0.85rem; color:#6B7280;'>({t_prio} | {t_min}분)</span>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                
                with col_del:
                    if st.button("🗑️", key=f"del_{t_id}"):
                        delete_task(t_id)
                        st.toast("삭제되었습니다.", icon="🗑️")
                        st.rerun()

    with tab2:
        st.subheader("📈 공부 분석 및 통계")
        
        if SUPABASE_CONNECTED:
            res = supabase_client.table("tasks").select("*").eq("username", st.session_state["username"]).execute()
            df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
        else:
            conn = get_sqlite_conn()
            df = pd.read_sql_query("SELECT * FROM tasks WHERE username = ?", conn, params=(st.session_state["username"],))
            conn.close()
        
        if df.empty:
            st.info("아직 기록된 공부 데이터가 없습니다.")
        else:
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.metric("총 등록 항목 수", f"{len(df)}개")
            with col_m2:
                completed_total = df[df['completed'] == True] if SUPABASE_CONNECTED else df[df['completed'] == 1]
                st.metric("총 완료한 항목", f"{len(completed_total)}개")
            with col_m3:
                total_hours = round(df['study_minutes'].sum() / 60, 1)
                st.metric("총 학습 계획 시간", f"{total_hours}시간")
            
            st.divider()
            
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.markdown("##### 📌 과목별 학습 비중 (시간 분)")
                subject_df = df.groupby('subject')['study_minutes'].sum().reset_index()
                st.bar_chart(subject_df.set_index('subject'))
                
            with col_chart2:
                st.markdown("##### 📅 날짜별 등록된 할 일 수")
                date_df = df.groupby('date')['id'].count().reset_index()
                date_df.rename(columns={'id': '할일수'}, inplace=True)
                st.line_chart(date_df.set_index('date'))

    with tab3:
        st.subheader(f"📝 {date_str} 오늘의 일기 & 총평")
        existing_memo = get_daily_memo(st.session_state["username"], date_str)
        memo_input = st.text_area("오늘 하루 공부를 돌이켜보며 잘한 점과 개선할 점을 적어보세요.", value=existing_memo, height=150)
        
        if st.button("피드백 저장하기", type="primary"):
            save_daily_memo(st.session_state["username"], date_str, memo_input)
            st.success("오늘의 피드백이 저장되었습니다!")



