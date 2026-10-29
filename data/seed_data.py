"""
seed_data.py
Creates realistic Manufacturing Enterprise database tables:
  1. plants (plant_id, plant_name, city, country, max_daily_capacity)
  2. production_lines (line_id, plant_id, line_name, line_type, status)
  3. products (product_id, product_name, category, unit_cost, target_cycle_time_sec)
  4. production_runs (run_id, plant_id, line_id, product_id, run_date, shift, planned_qty, actual_qty, defect_qty, downtime_mins, oee_pct)
  5. machine_maintenance (maintenance_id, plant_id, machine_name, issue_category, downtime_hours, repair_cost, maintenance_date)
  6. noise_canteen_menu (Noise table to test RAG filtering)
  7. noise_visitor_logs (Noise table to test RAG filtering)
"""

import os
import sys
from datetime import date
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

def get_connection_url(fallback_sqlite=False):
    """Builds database connection URL from environment variables."""
    if fallback_sqlite:
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "manufacturing_db.db"))
        return f"sqlite:///{db_path}"
    
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url
    
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "company_db")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"

def seed_database(engine):
    """Populates manufacturing schema and realistic operational records."""
    print(f"Connecting to database: {engine.url.render_as_string(hide_password=True)}...")
    
    is_sqlite = engine.dialect.name == "sqlite"
    pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "SERIAL PRIMARY KEY"
    drop_suffix = ";" if is_sqlite else " CASCADE;"
    
    with engine.begin() as conn:
        tables_to_drop = [
            "machine_maintenance", "production_runs", "production_lines", 
            "products", "plants", "noise_canteen_menu", "noise_visitor_logs"
        ]
        for tbl in tables_to_drop:
            conn.execute(text(f"DROP TABLE IF EXISTS {tbl}{drop_suffix}"))
            
        print("Creating manufacturing tables...")
        
        # 1. Plants (Manufacturing Facilities)
        conn.execute(text(f"""
            CREATE TABLE plants (
                plant_id {pk_type},
                plant_name VARCHAR(100) NOT NULL,
                city VARCHAR(100) NOT NULL,
                country VARCHAR(100) NOT NULL,
                max_daily_capacity INT NOT NULL
            );
        """))

        # 2. Production Lines
        conn.execute(text(f"""
            CREATE TABLE production_lines (
                line_id {pk_type},
                plant_id INT REFERENCES plants(plant_id),
                line_name VARCHAR(100) NOT NULL,
                line_type VARCHAR(50) NOT NULL, -- Assembly, Machining, Packaging, Stamping
                status VARCHAR(50) NOT NULL     -- Active, Maintenance, Idle
            );
        """))

        # 3. Products / Manufactured Components
        conn.execute(text(f"""
            CREATE TABLE products (
                product_id {pk_type},
                product_name VARCHAR(150) NOT NULL,
                category VARCHAR(100) NOT NULL, -- Hydraulics, Powertrain, Electronics, Fasteners
                unit_cost NUMERIC(10, 2) NOT NULL,
                target_cycle_time_sec INT NOT NULL
            );
        """))

        # 4. Production Runs (Batches, OEE, Scrap, Downtime)
        conn.execute(text(f"""
            CREATE TABLE production_runs (
                run_id {pk_type},
                plant_id INT REFERENCES plants(plant_id),
                line_id INT REFERENCES production_lines(line_id),
                product_id INT REFERENCES products(product_id),
                run_date DATE NOT NULL,
                shift VARCHAR(20) NOT NULL,       -- Morning, Afternoon, Night
                planned_qty INT NOT NULL,
                actual_qty INT NOT NULL,
                defect_qty INT NOT NULL,
                downtime_mins INT NOT NULL,
                oee_pct NUMERIC(5, 2) NOT NULL    -- Overall Equipment Effectiveness (e.g. 84.50%)
            );
        """))

        # 5. Machine Maintenance & Downtime Costs
        conn.execute(text(f"""
            CREATE TABLE machine_maintenance (
                maintenance_id {pk_type},
                plant_id INT REFERENCES plants(plant_id),
                machine_name VARCHAR(100) NOT NULL,
                issue_category VARCHAR(100) NOT NULL, -- Hydraulic Leak, Sensor Fault, Motor Overheating, Gear Wear
                downtime_hours NUMERIC(6, 2) NOT NULL,
                repair_cost NUMERIC(10, 2) NOT NULL,
                maintenance_date DATE NOT NULL
            );
        """))

        # Noise Tables (Testing RAG table filtering)
        conn.execute(text(f"""
            CREATE TABLE noise_canteen_menu (
                menu_id {pk_type},
                dish_name VARCHAR(100),
                day_of_week VARCHAR(20),
                calories INT
            );
        """))

        conn.execute(text(f"""
            CREATE TABLE noise_visitor_logs (
                badge_id {pk_type},
                visitor_name VARCHAR(100),
                checkin_time VARCHAR(50)
            );
        """))

        print("Inserting realistic manufacturing records...")

        # Insert Plants
        conn.execute(text("""
            INSERT INTO plants (plant_name, city, country, max_daily_capacity) VALUES
            ('Detroit Heavy Assembly', 'Detroit', 'USA', 15000),
            ('Munich Powertrain Hub', 'Munich', 'Germany', 22000),
            ('Tokyo Micro-Fab & Electronics', 'Yokohama', 'Japan', 35000),
            ('Monterrey Stamping Works', 'Monterrey', 'Mexico', 18000);
        """))

        # Insert Lines
        conn.execute(text("""
            INSERT INTO production_lines (plant_id, line_name, line_type, status) VALUES
            (1, 'Line A - Chassis Welding', 'Assembly', 'Active'),
            (1, 'Line B - Final Inspection', 'Packaging', 'Active'),
            (2, 'Line 1 - Engine Block CNC', 'Machining', 'Active'),
            (2, 'Line 2 - Gearbox Assembly', 'Assembly', 'Active'),
            (3, 'Cleanroom Line Alpha', 'Assembly', 'Active'),
            (3, 'SMT Board Mount Line', 'Assembly', 'Maintenance'),
            (4, 'Press Line 500T', 'Stamping', 'Active');
        """))

        # Insert Products
        conn.execute(text("""
            INSERT INTO products (product_name, category, unit_cost, target_cycle_time_sec) VALUES
            ('Heavy-Duty Hydraulic Cylinder', 'Hydraulics', 450.00, 120),
            ('High-Torque EV Motor Rotor', 'Powertrain', 320.00, 95),
            ('Electronic Engine Control Unit (ECU)', 'Electronics', 185.00, 45),
            ('Cast Steel Gear Housing', 'Powertrain', 240.00, 160),
            ('Precision Industrial Pressure Sensor', 'Electronics', 85.00, 30);
        """))

        # Insert Production Runs (with planned, actual, defects, downtime, OEE)
        runs_data = [
            (1, 1, 1, '2026-09-20', 'Morning',   1200, 1150, 24, 35, 87.5),
            (1, 1, 1, '2026-09-20', 'Afternoon', 1200, 1100, 38, 55, 81.2),
            (1, 1, 1, '2026-09-20', 'Night',     1000,  920, 45, 75, 74.0),
            (2, 3, 2, '2026-09-20', 'Morning',   2500, 2480, 12, 10, 94.2),
            (2, 3, 2, '2026-09-20', 'Afternoon', 2500, 2410, 22, 25, 89.8),
            (2, 4, 4, '2026-09-20', 'Morning',   1800, 1720, 31, 40, 85.0),
            (3, 5, 3, '2026-09-20', 'Morning',   5000, 4950, 18, 15, 96.0),
            (3, 5, 3, '2026-09-20', 'Afternoon', 5000, 4890, 35, 30, 91.5),
            (3, 5, 5, '2026-09-21', 'Morning',   4000, 3920, 28, 20, 93.0),
            (4, 7, 4, '2026-09-21', 'Morning',   2000, 1850, 65, 80, 78.4),
            (4, 7, 4, '2026-09-21', 'Afternoon', 2000, 1910, 42, 45, 83.1),
            (1, 2, 1, '2026-09-22', 'Morning',   1500, 1470, 19, 15, 92.0),
            (2, 3, 2, '2026-09-22', 'Morning',   2500, 2460, 15, 12, 93.5),
            (3, 5, 3, '2026-09-22', 'Night',     4500, 4310, 52, 60, 82.0),
        ]

        for p_id, l_id, pr_id, r_date, shift, plan, act, defs, down, oee in runs_data:
            conn.execute(text(f"""
                INSERT INTO production_runs 
                (plant_id, line_id, product_id, run_date, shift, planned_qty, actual_qty, defect_qty, downtime_mins, oee_pct)
                VALUES ({p_id}, {l_id}, {pr_id}, '{r_date}', '{shift}', {plan}, {act}, {defs}, {down}, {oee});
            """))

        # Insert Machine Maintenance Records
        maint_data = [
            (1, 'Robotic Welder #4', 'Hydraulic Leak', 4.5, 3200.00, '2026-09-15'),
            (2, '5-Axis CNC Milling Center', 'Motor Overheating', 6.0, 5800.00, '2026-09-17'),
            (3, 'High-Speed SMT Placement Head', 'Sensor Fault', 2.0, 1400.00, '2026-09-18'),
            (4, 'Heavy Hydraulic Stamping Press', 'Gear Wear', 8.5, 9200.00, '2026-09-19'),
            (1, 'Conveyor Drive System #2', 'Sensor Fault', 1.5, 750.00, '2026-09-21'),
            (2, 'Automated Coolant Chiller', 'Hydraulic Leak', 3.0, 2100.00, '2026-09-22'),
        ]

        for p_id, m_name, cat, hrs, cost, m_date in maint_data:
            conn.execute(text(f"""
                INSERT INTO machine_maintenance 
                (plant_id, machine_name, issue_category, downtime_hours, repair_cost, maintenance_date)
                VALUES ({p_id}, '{m_name}', '{cat}', {hrs}, {cost}, '{m_date}');
            """))

        # Noise data
        conn.execute(text("""
            INSERT INTO noise_canteen_menu (dish_name, day_of_week, calories) VALUES
            ('Grilled Salmon Salad', 'Monday', 450),
            ('Beef Stroganoff', 'Tuesday', 780);
        """))

    print("Manufacturing database successfully seeded!")

if __name__ == "__main__":
    use_sqlite = "--sqlite" in sys.argv
    try:
        url = get_connection_url(fallback_sqlite=use_sqlite)
        engine = create_engine(url)
        seed_database(engine)
    except Exception as e:
        print(f"\n[!] Error connecting: {e}")
        print("Run `python data/seed_data.py --sqlite` for local mock database testing.")
