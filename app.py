import streamlit as st
import pandas as pd
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError
from bson.objectid import ObjectId
from datetime import datetime
import time
import io

# --- CONFIGURATION ---
st.set_page_config(page_title="HR Manager", layout="wide")

# --- DATABASE CONNECTION (UPDATED) ---
@st.cache_resource
def init_connection():
    """
    Connects to MongoDB using the robust ServerApi version 1.
    """
    try:
        # 1. Get the Connection String (URI)
        if "MONGO_URI" in st.secrets:
            uri = st.secrets["MONGO_URI"]
        else:
            # Fallback for local testing if secrets file is missing
            print("⚠️ Using Localhost (No Secrets Found)...")
            uri = "mongodb://localhost:27017/"

        # 2. Create a new client and connect to the server (Your Snippet)
        client = MongoClient(uri, server_api=ServerApi('1'))

        # 3. Send a ping to confirm a successful connection
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
        
        return client

    except OperationFailure:
        st.error("🚨 **Authentication Failed!** Please check your Username and Password in Streamlit Secrets.")
        st.stop()
    except ServerSelectionTimeoutError:
        st.error("🚨 **Connection Failed!** Check your Network Access in Atlas. Ensure '0.0.0.0/0' is active.")
        st.stop()
    except Exception as e:
        st.error(f"🚨 **Error:** {e}")
        return None

client = init_connection()

# Initialize Collections
if client:
    # We force the database name here to ensure we don't use the default 'test'
    db_name = "EmployeeManagementDB"
    # If the URI has a DB name, PyMongo uses it, otherwise we pick it explicitly
    db = client[db_name]
    
    employees_col = db["employees"]
    salaries_col = db["salaries"]
    
    # Create Indexes safely
    try:
        employees_col.create_index("email", unique=True)
        salaries_col.create_index([("employeeId", 1), ("month", 1)], unique=True)
    except Exception:
        pass

# --- UTILITY FUNCTIONS ---

def serialize_doc(doc):
    doc["_id"] = str(doc["_id"])
    return doc

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    output.seek(0)
    return output

# --- BACKEND LOGIC ---

def create_employee(emp_id, name, email, designation):
    try:
        if employees_col.find_one({"employeeId": emp_id}):
            return False, "Employee ID already exists."
        
        employees_col.insert_one({
            "employeeId": emp_id,
            "name": name,
            "email": email,
            "designation": designation,
            "status": "Active",
            "joinedDate": datetime.now()
        })
        return True, "Employee onboarded successfully."
    except Exception as e:
        if "duplicate key" in str(e):
            return False, "Email already registered."
        return False, f"Error: {e}"

def get_employees(active_only=True):
    query = {"status": "Active"} if active_only else {}
    return [serialize_doc(doc) for doc in employees_col.find(query)]

def update_employee(obj_id, name, email, designation):
    employees_col.update_one(
        {"_id": ObjectId(obj_id)},
        {"$set": {"name": name, "email": email, "designation": designation}}
    )

def delete_employee(obj_id):
    employees_col.update_one(
        {"_id": ObjectId(obj_id)},
        {"$set": {"status": "Inactive"}}
    )

def credit_salary(emp_id, amount, month_str):
    try:
        emp = employees_col.find_one({"employeeId": emp_id})
        if not emp: return False, "Employee not found."
        
        salaries_col.insert_one({
            "employeeId": emp_id,
            "employeeName": emp["name"],
            "amount": float(amount),
            "month": month_str,
            "creditedDate": datetime.now()
        })
        return True, f"Salary credited for {emp['name']}."
    except Exception as e:
        if "duplicate key" in str(e):
            return False, "Duplicate payment prevented for this month."
        return False, str(e)

def get_salary_data(month_str):
    return [serialize_doc(doc) for doc in salaries_col.find({"month": month_str})]

# --- FRONTEND UI ---

st.title("🏢 Employee & Payroll System")

menu = st.sidebar.radio("Main Menu", ["👥 Employee Management", "💰 Salary Processing", "📊 Reports & Export"])

# 1. EMPLOYEE MANAGEMENT
if menu == "👥 Employee Management":
    st.header("Employee Directory")
    tab1, tab2 = st.tabs(["View / Edit Staff", "Add New Employee"])
    
    with tab1:
        employees = get_employees()
        if employees:
            df = pd.DataFrame(employees)
            st.dataframe(df[["employeeId", "name", "email", "designation", "status"]], use_container_width=True)
            
            st.divider()
            st.subheader("Edit Employee Details")
            emp_dict = {e["employeeId"]: e["name"] for e in employees}
            selected_id = st.selectbox("Select Employee", list(emp_dict.keys()), 
                                     format_func=lambda x: f"{emp_dict[x]} ({x})")
            
            if selected_id:
                curr = next(e for e in employees if e["employeeId"] == selected_id)
                with st.form("edit_emp"):
                    c1, c2 = st.columns(2)
                    n_name = c1.text_input("Name", curr['name'])
                    n_email = c2.text_input("Email", curr['email'])
                    n_role = st.text_input("Designation", curr['designation'])
                    
                    b1, b2 = st.columns([1, 4])
                    if b1.form_submit_button("Update"):
                        update_employee(curr['_id'], n_name, n_email, n_role)
                        st.success("Updated!")
                        time.sleep(1)
                        st.rerun()
                    if b2.form_submit_button("Remove (Soft Delete)", type="primary"):
                        delete_employee(curr['_id'])
                        st.warning("Employee removed.")
                        time.sleep(1)
                        st.rerun()
        else:
            st.info("No active employees found.")
            
    with tab2:
        st.subheader("Onboard New Staff")
        with st.form("add_emp"):
            c1, c2 = st.columns(2)
            id_in = c1.text_input("Employee ID", placeholder="EMP001")
            name_in = c2.text_input("Full Name")
            email_in = st.text_input("Email")
            role_in = st.text_input("Designation")
            if st.form_submit_button("Create Employee"):
                if id_in and name_in:
                    ok, msg = create_employee(id_in, name_in, email_in, role_in)
                    if ok: st.success(msg)
                    else: st.error(msg)
                else:
                    st.warning("ID and Name are required.")

# 2. SALARY PROCESSING
elif menu == "💰 Salary Processing":
    st.header("Payroll")
    curr_month = datetime.now().strftime("%Y-%m")
    sel_month = st.sidebar.text_input("Payroll Month (YYYY-MM)", value=curr_month)
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.info("Credit Salary")
        staff = get_employees()
        staff_map = {e["employeeId"]: e["name"] for e in staff}
        with st.form("salary_form"):
            p_id = st.selectbox("Employee", staff_map.keys(), format_func=lambda x: staff_map[x])
            p_amt = st.number_input("Amount", min_value=0.0, step=500.0)
            if st.form_submit_button("Credit"):
                ok, msg = credit_salary(p_id, p_amt, sel_month)
                if ok: st.success(msg)
                else: st.error(msg)
    with col2:
        st.caption(f"Transactions for {sel_month}")
        txns = get_salary_data(sel_month)
        if txns:
            st.dataframe(pd.DataFrame(txns)[["employeeId", "employeeName", "amount", "creditedDate"]], 
                         use_container_width=True)
        else:
            st.write("No transactions yet.")

# 3. REPORTING & EXPORT
elif menu == "📊 Reports & Export":
    st.header("Generate Reports")
    report_month = st.text_input("Filter by Month (YYYY-MM)", value=datetime.now().strftime("%Y-%m"))
    
    if st.button("Load Data"):
        data = get_salary_data(report_month)
        if data:
            df = pd.DataFrame(data)
            export_df = df[["employeeId", "employeeName", "amount", "month", "creditedDate"]]
            
            st.success(f"Loaded {len(data)} records for {report_month}")
            st.dataframe(export_df, use_container_width=True)
            st.write("### Download Options")
            c1, c2 = st.columns(2)
            
            csv_data = export_df.to_csv(index=False).encode('utf-8')
            c1.download_button("📄 Download as CSV", data=csv_data, file_name=f"Salary_{report_month}.csv", mime="text/csv")
            
            excel_data = to_excel(export_df)
            c2.download_button("📗 Download as Excel", data=excel_data, file_name=f"Salary_{report_month}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.warning("No data found.")
