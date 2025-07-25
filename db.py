import sqlite3
import pandas as pd
from typing import List, Tuple, Optional

class CompanyDatabase:
    def __init__(self, db_name: str = "company.db"):
        self.db_name = db_name
    
    def get_connection(self):
        """Create and return a database connection"""
        return sqlite3.connect(self.db_name)
    
    def create_tables(self):
        """Create employee, policies, and acknowledgements tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Drop tables if they already exist (for reruns)
            cursor.execute("DROP TABLE IF EXISTS acknowledgements;")
            cursor.execute("DROP TABLE IF EXISTS employee;")
            cursor.execute("DROP TABLE IF EXISTS policies;")
            
            # Create employee table
            cursor.execute("""
            CREATE TABLE employee (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER,
                gender TEXT,
                position TEXT,
                department TEXT,
                work_mode TEXT CHECK(work_mode IN ('Remote', 'Onsite')),
                email 
            );
            """)
            
            # Create policies table
            cursor.execute("""
            CREATE TABLE policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_text TEXT NOT NULL,
                department TEXT,
                work_mode TEXT CHECK(work_mode IN ('Remote', 'Onsite')),
                status TEXT CHECK(status IN ('Implemented', 'Not Implemented'))
            );
            """)
            
            # Create acknowledgements table
            cursor.execute("""
            CREATE TABLE acknowledgements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                status TEXT CHECK(status IN ('ack', 'nak', 'not responded')) DEFAULT 'not responded',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (policy_id) REFERENCES policies (id) ON DELETE CASCADE,
                FOREIGN KEY (employee_id) REFERENCES employee (id) ON DELETE CASCADE,
                UNIQUE(policy_id, employee_id)
            );
            """)
            
            conn.commit()
            print("✅ Tables created successfully.")
            
        except sqlite3.Error as e:
            print(f"❌ Error creating tables: {e}")
        finally:
            conn.close()
    
    def insert_employee(self, name: str, age: int, gender: str, position: str, 
                       department: str, work_mode: str, email: str) -> bool:
        """Insert a single employee record"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            INSERT INTO employee (name, age, gender, position, department, work_mode, email)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, age, gender, position, department, work_mode, email))
            
            conn.commit()
            print(f"✅ Employee '{name}' added successfully.")
            return True
            
        except sqlite3.Error as e:
            print(f"❌ Error inserting employee: {e}")
            return False
        finally:
            conn.close()
    
    def insert_employees_bulk(self, employees: List[Tuple]):
        """Insert multiple employee records at once"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.executemany("""
            INSERT INTO employee (name, age, gender, position, department, work_mode, email)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, employees)
            
            conn.commit()
            print(f"✅ {len(employees)} employees added successfully.")
            
        except sqlite3.Error as e:
            print(f"❌ Error inserting employees: {e}")
        finally:
            conn.close()
    
    def get_eligible_employees_for_policy(self, department: str = None, work_mode: str = None) -> List[int]:
        """Get employee IDs that match the policy criteria"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Build query based on criteria
            conditions = []
            params = []
            
            if department:
                conditions.append("department = ?")
                params.append(department)
            
            if work_mode:
                conditions.append("work_mode = ?")
                params.append(work_mode)
            
            if conditions:
                query = f"SELECT id FROM employee WHERE {' AND '.join(conditions)}"
                cursor.execute(query, params)
            else:
                # If no specific criteria, get all employees
                cursor.execute("SELECT id FROM employee")
            
            employee_ids = [row[0] for row in cursor.fetchall()]
            return employee_ids
            
        except sqlite3.Error as e:
            print(f"❌ Error getting eligible employees: {e}")
            return []
        finally:
            conn.close()
    
    def create_acknowledgement_entries(self, policy_id: int, employee_ids: List[int]):
        """Create acknowledgement entries for a policy and its eligible employees"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Create acknowledgement entries for each eligible employee
            acknowledgement_data = [(policy_id, emp_id, 'not responded') for emp_id in employee_ids]
            
            cursor.executemany("""
            INSERT INTO acknowledgements (policy_id, employee_id, status)
            VALUES (?, ?, ?)
            """, acknowledgement_data)
            
            conn.commit()
            print(f"✅ Created {len(employee_ids)} acknowledgement entries for policy ID {policy_id}.")
            
        except sqlite3.Error as e:
            print(f"❌ Error creating acknowledgement entries: {e}")
        finally:
            conn.close()
    
    def insert_policy(self, policy_text: str, department: str, work_mode: str, status: str) -> bool:
        """Insert a single policy record and create acknowledgement entries"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Insert the policy
            cursor.execute("""
            INSERT INTO policies (policy_text, department, work_mode, status)
            VALUES (?, ?, ?, ?)
            """, (policy_text, department, work_mode, status))
            
            policy_id = cursor.lastrowid
            conn.commit()
            
            # Get eligible employees for this policy
            eligible_employees = self.get_eligible_employees_for_policy(department, work_mode)
            
            if eligible_employees:
                # Create acknowledgement entries
                self.create_acknowledgement_entries(policy_id, eligible_employees)
                print(f"✅ Policy added successfully with {len(eligible_employees)} acknowledgement entries.")
            else:
                print("✅ Policy added successfully (no eligible employees found).")
            
            return True
            
        except sqlite3.Error as e:
            print(f"❌ Error inserting policy: {e}")
            return False
        finally:
            conn.close()
    
    def insert_policies_bulk(self, policies: List[Tuple]):
        """Insert multiple policy records at once and create acknowledgement entries"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            for policy_data in policies:
                policy_text, department, work_mode, status = policy_data
                
                # Insert the policy
                cursor.execute("""
                INSERT INTO policies (policy_text, department, work_mode, status)
                VALUES (?, ?, ?, ?)
                """, (policy_text, department, work_mode, status))
                
                policy_id = cursor.lastrowid
                
                # Get eligible employees for this policy
                eligible_employees = self.get_eligible_employees_for_policy(department, work_mode)
                
                if eligible_employees:
                    # Create acknowledgement entries
                    acknowledgement_data = [(policy_id, emp_id, 'not responded') for emp_id in eligible_employees]
                    cursor.executemany("""
                    INSERT INTO acknowledgements (policy_id, employee_id, status)
                    VALUES (?, ?, ?)
                    """, acknowledgement_data)
            
            conn.commit()
            print(f"✅ {len(policies)} policies added successfully with acknowledgement entries.")
            
        except sqlite3.Error as e:
            print(f"❌ Error inserting policies: {e}")
        finally:
            conn.close()
    
    def update_acknowledgement_status(self, policy_id: int, employee_id: int, status: str) -> bool:
        """Update acknowledgement status for a specific policy-employee combination"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if status not in ['ack', 'nak', 'not responded']:
            print("❌ Invalid status. Must be 'ack', 'nak', or 'not responded'.")
            conn.close()
            return False
        
        try:
            cursor.execute("""
            UPDATE acknowledgements 
            SET status = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE policy_id = ? AND employee_id = ?
            """, (status, policy_id, employee_id))
            
            if cursor.rowcount > 0:
                conn.commit()
                print(f"✅ Acknowledgement status updated to '{status}' for policy ID {policy_id}, employee ID {employee_id}.")
                return True
            else:
                print(f"❌ No acknowledgement entry found for policy ID {policy_id}, employee ID {employee_id}.")
                return False
                
        except sqlite3.Error as e:
            print(f"❌ Error updating acknowledgement status: {e}")
            return False
        finally:
            conn.close()
    
    def update_employee(self, employee_id: int, **kwargs) -> bool:
        """Update employee data by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Build dynamic update query
        valid_fields = ['name', 'age', 'gender', 'position', 'department', 'work_mode', 'email']
        updates = []
        values = []
        
        for field, value in kwargs.items():
            if field in valid_fields:
                updates.append(f"{field} = ?")
                values.append(value)
        
        if not updates:
            print("❌ No valid fields provided for update.")
            conn.close()
            return False
        
        values.append(employee_id)  # Add ID for WHERE clause
        
        try:
            query = f"UPDATE employee SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, values)
            
            if cursor.rowcount > 0:
                conn.commit()
                print(f"✅ Employee ID {employee_id} updated successfully.")
                return True
            else:
                print(f"❌ No employee found with ID {employee_id}.")
                return False
                
        except sqlite3.Error as e:
            print(f"❌ Error updating employee: {e}")
            return False
        finally:
            conn.close()
    
    def update_policy(self, policy_id: int, **kwargs) -> bool:
        """Update policy data by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Build dynamic update query
        valid_fields = ['policy_text', 'department', 'work_mode', 'status']
        updates = []
        values = []
        
        for field, value in kwargs.items():
            if field in valid_fields:
                updates.append(f"{field} = ?")
                values.append(value)
        
        if not updates:
            print("❌ No valid fields provided for update.")
            conn.close()
            return False
        
        values.append(policy_id)  # Add ID for WHERE clause
        
        try:
            query = f"UPDATE policies SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, values)
            
            if cursor.rowcount > 0:
                conn.commit()
                print(f"✅ Policy ID {policy_id} updated successfully.")
                return True
            else:
                print(f"❌ No policy found with ID {policy_id}.")
                return False
                
        except sqlite3.Error as e:
            print(f"❌ Error updating policy: {e}")
            return False
        finally:
            conn.close()
    
    def delete_employee(self, employee_id: int) -> bool:
        """Delete an employee by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM employee WHERE id = ?", (employee_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                print(f"✅ Employee ID {employee_id} deleted successfully.")
                return True
            else:
                print(f"❌ No employee found with ID {employee_id}.")
                return False
                
        except sqlite3.Error as e:
            print(f"❌ Error deleting employee: {e}")
            return False
        finally:
            conn.close()
    
    def delete_policy(self, policy_id: int) -> bool:
        """Delete a policy by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM policies WHERE id = ?", (policy_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                print(f"✅ Policy ID {policy_id} deleted successfully.")
                return True
            else:
                print(f"❌ No policy found with ID {policy_id}.")
                return False
                
        except sqlite3.Error as e:
            print(f"❌ Error deleting policy: {e}")
            return False
        finally:
            conn.close()
    
    def delete_employees_by_department(self, department: str) -> int:
        """Delete all employees from a specific department"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM employee WHERE department = ?", (department,))
            deleted_count = cursor.rowcount
            conn.commit()
            print(f"✅ {deleted_count} employees from {department} department deleted.")
            return deleted_count
            
        except sqlite3.Error as e:
            print(f"❌ Error deleting employees: {e}")
            return 0
        finally:
            conn.close()
    
    def view_employees(self) -> pd.DataFrame:
        """View all employees"""
        conn = self.get_connection()
        
        try:
            df = pd.read_sql_query("SELECT * FROM employee", conn)
            print("📋 Employee Table:")
            print(df)
            return df
            
        except sqlite3.Error as e:
            print(f"❌ Error reading employees: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def view_policies(self) -> pd.DataFrame:
        """View all policies"""
        conn = self.get_connection()
        
        try:
            df = pd.read_sql_query("SELECT * FROM policies", conn)
            print("📋 Policies Table:")
            print(df)
            return df
            
        except sqlite3.Error as e:
            print(f"❌ Error reading policies: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def view_acknowledgements(self) -> pd.DataFrame:
        """View all acknowledgements with employee and policy details"""
        conn = self.get_connection()
        
        try:
            query = """
            SELECT 
                a.id,
                a.policy_id,
                p.policy_text,
                a.employee_id,
                e.name as employee_name,
                e.email as employee_email,
                e.department,
                e.work_mode,
                a.status,
                a.created_at,
                a.updated_at
            FROM acknowledgements a
            JOIN policies p ON a.policy_id = p.id
            JOIN employee e ON a.employee_id = e.id
            ORDER BY a.policy_id, e.name
            """
            df = pd.read_sql_query(query, conn)
            print("📋 Acknowledgements Table:")
            print(df)
            return df
            
        except sqlite3.Error as e:
            print(f"❌ Error reading acknowledgements: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def get_policy_acknowledgement_summary(self, policy_id: int) -> pd.DataFrame:
        """Get acknowledgement summary for a specific policy"""
        conn = self.get_connection()
        
        try:
            query = """
            SELECT 
                p.policy_text,
                a.status,
                COUNT(*) as count
            FROM acknowledgements a
            JOIN policies p ON a.policy_id = p.id
            WHERE a.policy_id = ?
            GROUP BY a.status
            """
            df = pd.read_sql_query(query, conn, params=[policy_id])
            print(f"📊 Acknowledgement Summary for Policy ID {policy_id}:")
            print(df)
            return df
            
        except sqlite3.Error as e:
            print(f"❌ Error getting policy acknowledgement summary: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def search_employees(self, **kwargs) -> pd.DataFrame:
        """Search employees by various criteria"""
        conn = self.get_connection()
        
        conditions = []
        values = []
        
        for field, value in kwargs.items():
            if field in ['name', 'gender', 'position', 'department', 'work_mode']:
                conditions.append(f"{field} = ?")
                values.append(value)
            elif field == 'min_age':
                conditions.append("age >= ?")
                values.append(value)
            elif field == 'max_age':
                conditions.append("age <= ?")
                values.append(value)
        
        if not conditions:
            print("❌ No valid search criteria provided.")
            conn.close()
            return pd.DataFrame()
        
        try:
            query = f"SELECT * FROM employee WHERE {' AND '.join(conditions)}"
            df = pd.read_sql_query(query, conn, params=values)
            return df['email']
            
        except sqlite3.Error as e:
            print(f"❌ Error searching employees: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def initialize_sample_data(self):
        """Initialize database with sample data"""
        # Sample employees
        employees = [
            ("Muhammad Hamza1", 29, "Male", "Software Engineer", "IT", "Remote", "i210869@nu.edu.pk"),
            ("Muhammad Hamza2", 28, "Male", "Software Developer", "IT", "Remote", "mhamzacpp@gmail.com"),
        ]
        
        # Sample policies
        policies = [
            ("All employees must change passwords every 90 days.", "IT", "Remote", "Not Implemented"),
            ("Hybrid employees must be in-office at least twice a week.", "HR", "Onsite", "Not Implemented"),
            ("Compliance audits are to be done quarterly.", "Compliance", "Onsite", "Not Implemented"),
        ]
        
        self.insert_employees_bulk(employees)
        self.insert_policies_bulk(policies)
    

    def search_employees_full(self, **kwargs):
        """
        Search employees by various criteria and return full employee records
        (Modified version of search_employees that returns full records instead of just emails)
        """
        conn = self.get_connection()
        
        conditions = []
        values = []
        
        for field, value in kwargs.items():
            if field in ['name', 'gender', 'position', 'department', 'work_mode']:
                conditions.append(f"{field} = ?")
                values.append(value)
            elif field == 'min_age':
                conditions.append("age >= ?")
                values.append(value)
            elif field == 'max_age':
                conditions.append("age <= ?")
                values.append(value)
        
        if not conditions:
            print("❌ No valid search criteria provided.")
            conn.close()
            return pd.DataFrame()
        
        try:
            query = f"SELECT * FROM employee WHERE {' AND '.join(conditions)}"
            df = pd.read_sql_query(query, conn, params=values)
            return df
            
        except sqlite3.Error as e:
            print(f"❌ Error searching employees: {e}")
            return pd.DataFrame()
        finally:
            conn.close()


# Example usage and demo
def main():
    # Initialize database
    db = CompanyDatabase()
    
    # Create tables
    db.create_tables()
    
    # Initialize with sample data
    db.initialize_sample_data()
    
    print("\n" + "="*50)
    print("VIEWING ALL DATA")
    print("="*50)
    db.view_employees()
    print()
    db.view_policies()
    print()
    db.view_acknowledgements()
    
    print("\n" + "="*50)
    print("UPDATING ACKNOWLEDGEMENT STATUS")
    print("="*50)
    # Update some acknowledgement statuses
    db.update_acknowledgement_status(1, 1, 'ack')  # Policy 1, Employee 1 acknowledges
    db.update_acknowledgement_status(1, 4, 'nak')  # Policy 1, Employee 4 does not acknowledge
    
    print("\n" + "="*50)
    print("POLICY ACKNOWLEDGEMENT SUMMARY")
    print("="*50)
    db.get_policy_acknowledgement_summary(1)
    
    print("\n" + "="*50)
    print("ADDING NEW POLICY")
    print("="*50)
    db.insert_policy("All IT staff must complete security training by end of month.", "IT", "Remote", "Not Implemented")
    
    print("\n" + "="*50)
    print("UPDATED ACKNOWLEDGEMENTS")
    print("="*50)
    db.view_acknowledgements()

if __name__ == "__main__":
    main()