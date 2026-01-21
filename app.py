import streamlit as st
import pandas as pd
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError
from bson.objectid import ObjectId
from datetime import datetime
import time
import io

# --- APP CONFIGURATION ---
st.set_page_config(
    page_title="Employee Management System",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DATABASE CONNECTION HANDLER ---
@st.cache_resource
def get_db_connection():
    """
    Establishes a connection to MongoDB using enterprise standards.
    """
    try:
        if "MONGO_URI" in st.secrets:
            uri = st.secrets["MONGO_URI"]
        else:
            uri = "mongodb://localhost:27017/"

        client = MongoClient(uri, server_api=ServerApi('1'), serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        return client

    except OperationFailure:
        st.error("System Error: Authentication failed. Please verify database credentials.")
        st.stop()
    except ServerSelectionTimeoutError:
        st.error("Network Error: Unable to reach database. Verify network allow-list (0.0.0.0/0).")
        st.stop()
    except Exception as e:
        st.error(f"Critical Error: {str(e)}")
        return None

# --- DATA LAYER (CRUD OPERATIONS) ---

def fetch_employees(active_only=True):
    client = get_db_connection()
    if not client: return []
    
    db = client["EmployeeManagementDB"]
    query = {"status": "Active"} if active_only else {}
    
    cursor = db["employees"].find(query)
    data = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        data.append(doc)
    return data

def register_employee(emp_id, name, email, role):
    client = get_db_connection()
    db = client["EmployeeManagementDB"]
    
    if db["employees"].find_one({"employeeId": emp_id}):
        return False, "Employee ID is already in use."
    
    new_record = {
        "employeeId": emp_id,
        "name": name,
        "email": email,
        "designation": role,
        "status": "Active",
        "joinedDate": datetime.now()
    }
    
    try:
        db["employees"].insert_one(new_record)
        return True, "Employee registered successfully."
    except Exception as e:
        if "duplicate key" in str(e):
            return False, "This email address is already registered."
        return False, f"Database error: {str(e)}"

def update_employee_record(uid, name, email, role):
    client = get_db_connection()
    db = client["EmployeeManagementDB"]
    try:
        db["employees"].update_one(
            {"_id": ObjectId(uid)},
            {"$set": {"name": name, "email": email, "designation": role}}
        )
        return True
    except Exception:
        return False

def archive_employee(uid):
    client = get_db_connection()
    db = client["EmployeeManagementDB"]
    try:
        db["employees"].update_one(
            {"_id": ObjectId(uid)},
            {"$set": {"status": "Inactive"}}
        )
        return True
    except Exception:
        return False

def process_payroll_transaction(emp_id, amount, month):
    client = get_db_connection()
    db = client["EmployeeManagementDB"]
    
    employee = db["employees"].find_one({"employeeId": emp_id})
    if not employee:
        return False, "Employee record not found."
    
    transaction = {
        "employeeId": emp_id,
        "employeeName": employee["name"],
        "amount": float(amount),
        "month": month,
        "processedDate": datetime.now()
    }
    
    try:
        db["salaries"].insert_one(transaction)
        return True, "Transaction processed successfully."
    except Exception as e:
        if "duplicate key" in str(e):
            return False, f"Salary for {month} has already been processed for this employee."
        return False, f"Error: {str(e)}"

def fetch_payroll_history(month=None):
    client = get_db_connection()
    db = client["EmployeeManagementDB"]
    
    query = {"month": month} if month else {}
    cursor = db["salaries"].find(query)
    
    data = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        data.append(doc)
    return data

def generate_excel(dataframe):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        dataframe.to_excel(writer, index=False, sheet_name='Report')
    buffer.seek(0)
    return buffer

# --- UI COMPONENTS ---

def render_dashboard():
    st.header("Executive Overview")
    employees = fetch_employees()
    current_month = datetime.now().strftime("%Y-%m")
    payroll = fetch_payroll_history(current_month)
    
    total_staff = len(employees)
    total_payout = sum(p['amount'] for p in payroll)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Active Employees", total_staff)
    col2.metric("Payroll Processed (Current Month)", f"${total_payout:,.2f}")
    col3.metric("Current Period", current_month)
    st.divider()

def render_employee_management():
    st.subheader("Employee Directory")
    col_table, col_form = st.columns([2, 1])
    
    with col_table:
        data = fetch_employees()
        if data:
            df = pd.DataFrame(data)
            st.dataframe(
                df,
                column_order=("employeeId", "name", "designation", "email", "status"),
                column_config={
                    "employeeId": "ID",
                    "name": "Full Name",
                    "designation": "Role",
                    "email": "Contact Email",
                    "status": st.column_config.TextColumn("Status")
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No records found.")

    with col_form:
        st.write("#### Actions")
        tab_add, tab_edit = st.tabs(["Add New", "Edit / Disable"])
        
        with tab_add:
            with st.form("new_hire_form"):
                st.write("**Register New Employee**")
                eid = st.text_input("Employee ID")
                name = st.text_input("Full Name")
                email = st.text_input("Email Address")
                role = st.text_input("Designation")
                
                if st.form_submit_button("Save Record", type="primary"):
                    if eid and name:
                        success, msg = register_employee(eid, name, email, role)
                        if success:
                            st.success(msg)
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("ID and Name are mandatory.")
        
        with tab_edit:
            st.write("**Update Records**")
            if data:
                options = {emp["employeeId"]: emp["name"] for emp in data}
                selected_id = st.selectbox("Search Employee", options.keys(), format_func=lambda x: f"{options[x]} ({x})")
                
                if selected_id:
                    current_emp = next(x for x in data if x["employeeId"] == selected_id)
                    with st.form("update_form"):
                        new_name = st.text_input("Full Name", value=current_emp["name"])
                        new_email = st.text_input("Email", value=current_emp["email"])
                        new_role = st.text_input("Designation", value=current_emp["designation"])
                        
                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("Update"):
                            update_employee_record(current_emp["_id"], new_name, new_email, new_role)
                            st.success("Updated.")
                            time.sleep(1)
                            st.rerun()
                        if c2.form_submit_button("Deactivate"):
                            archive_employee(current_emp["_id"])
                            st.warning("Deactivated.")
                            time.sleep(1)
                            st.rerun()

def render_payroll():
    st.subheader("Payroll Management")
    col_input, col_history = st.columns([1, 2])
    
    with col_input:
        st.markdown("#### Process Transaction")
        employees = fetch_employees()
        if not employees:
            st.warning("No active employees.")
        else:
            with st.form("payroll_form"):
                month_selector = st.text_input("Billing Period (YYYY-MM)", value=datetime.now().strftime("%Y-%m"))
                options = {emp["employeeId"]: emp["name"] for emp in employees}
                selected_emp = st.selectbox("Beneficiary", options.keys(), format_func=lambda x: options[x])
                amount = st.number_input("Net Salary Amount", min_value=0.0, step=100.0)
                
                if st.form_submit_button("Confirm Transaction", type="primary"):
                    success, msg = process_payroll_transaction(selected_emp, amount, month_selector)
                    if success:
                        st.success(msg)
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(msg)

    with col_history:
        st.markdown("#### Transaction History")
        filter_month = st.text_input("Filter History by Month", value=datetime.now().strftime("%Y-%m"), key="hist_filter")
        history = fetch_payroll_history(filter_month)
        if history:
            df = pd.DataFrame(history)
            st.dataframe(
                df,
                column_order=("processedDate", "employeeName", "amount", "month"),
                column_config={
                    "processedDate": st.column_config.DatetimeColumn("Date", format="D MMM YYYY, h:mm a"),
                    "employeeName": "Employee",
                    "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                    "month": "Period"
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info(f"No transactions found for {filter_month}")

def render_reports():
    st.subheader("Data Exports")
    st.markdown("Select a reporting period to download payroll data.")
    target_month = st.text_input("Reporting Period (YYYY-MM)", value=datetime.now().strftime("%Y-%m"))
    
    if st.button("Generate Report"):
        data = fetch_payroll_history(target_month)
        if data:
            df = pd.DataFrame(data)
            clean_df = df[["employeeId", "employeeName", "amount", "month", "processedDate"]]
            
            st.success(f"Report generated: {len(df)} records found.")
            st.write("---")
            col_csv, col_excel = st.columns(2)
            
            csv_buffer = clean_df.to_csv(index=False).encode('utf-8')
            col_csv.download_button("Download CSV Format", csv_buffer, f"Payroll_{target_month}.csv", "text/csv", use_container_width=True)
            
            excel_buffer = generate_excel(clean_df)
            col_excel.download_button("Download Excel Format", excel_buffer, f"Payroll_{target_month}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        else:
            st.warning("No data available.")

# --- MAIN NAVIGATION CONTROLLER ---

def main():
    # Initialize Session State for Page Navigation
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Dashboard"

    def navigate_to(page):
        st.session_state.current_page = page
        st.rerun()

    # SIDEBAR: Professional Button-Based Menu
    with st.sidebar:
        st.title("Admin Console")
        st.write("") # Spacer

        # Navigation Buttons (Active button gets 'primary' style, inactive gets 'secondary')
        
        if st.button("Dashboard", 
                     use_container_width=True, 
                     type="primary" if st.session_state.current_page == "Dashboard" else "secondary"):
            navigate_to("Dashboard")
            
        if st.button("Employees", 
                     use_container_width=True, 
                     type="primary" if st.session_state.current_page == "Employees" else "secondary"):
            navigate_to("Employees")
            
        if st.button("Payroll", 
                     use_container_width=True, 
                     type="primary" if st.session_state.current_page == "Payroll" else "secondary"):
            navigate_to("Payroll")
            
        if st.button("Reports", 
                     use_container_width=True, 
                     type="primary" if st.session_state.current_page == "Reports" else "secondary"):
            navigate_to("Reports")
        
        st.write("---")

    # MAIN CONTENT ROUTING
    if st.session_state.current_page == "Dashboard":
        render_dashboard()
    elif st.session_state.current_page == "Employees":
        render_employee_management()
    elif st.session_state.current_page == "Payroll":
        render_payroll()
    elif st.session_state.current_page == "Reports":
        render_reports()

if __name__ == "__main__":
    main()
