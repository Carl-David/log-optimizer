#!/usr/bin/env python3

import streamlit as st
import json
from typing import List, Dict, Tuple
import math
import random
import sqlite3

# Type definitions
Log = Dict[str, int]  # {"long": diameter} or {"short": diameter}
Tree = List[Log]      # [root_log, top_log]
Layer = List[Log]     # [log1, log2, log3, log4]

# TODO: Add as inputs
# TODO: Add lengths and långdragsinskning
DIAMETER_REDUCTION_MIN = 40  # Top log is 40-50mm narrower than root log
DIAMETER_REDUCTION_MAX = 50
LONG_LENGTH = 5150
SHORT_LENGTH = 4050
DIAMETER_REDUCTION_PER_METER = 10

def flatten_logs(logs):
    flat = []
    for log in logs:
        for k, v in log.items():
            flat.append({
                "length": k,
                "diameter": v,
                "source": "existing"
            })
    return flat

def get_log_diameter(log: Log) -> int:
    """Get the diameter of a log."""
    return log.get('long') or log.get('short')

def optimize_logs(existing_logs: List[Log], layers_count: int, root_log_diameters: List[int]) -> Tuple[List[Tree], List[Layer], Dict]:
    """
    Optimize logs.
    
    Args:
        existing_logs: List of existing logs in format [{"long": 260}, {"short": 210}, ...]
        layers_count: Number of layers (courses) to build
        root_log_diameters: Available root log diameters for new trees
    
    Returns:
        Tuple of (trees_to_cut, layers, summary)
    """
    total_logs_needed = layers_count * 4
    existing_logs_count = len(existing_logs)
    additional_logs_needed = total_logs_needed - existing_logs_count
    
    if additional_logs_needed < 0:
        raise ValueError(f"Too many existing logs. Need {total_logs_needed}, but have {existing_logs_count}")
    
    # Calculate how many trees we need to cut (each tree gives 2 logs)
    trees_to_cut = math.ceil(additional_logs_needed / 2)
    
    # Generate new logs from trees
    new_logs = []
    trees = []
    
    for i in range(trees_to_cut):
        # Select root diameter from allowed values
        root_diameter = root_log_diameters[i % len(root_log_diameters)]
        
        # Random diameter reduction between 40-50mm
        diameter_reduction = random.randint(DIAMETER_REDUCTION_MIN, DIAMETER_REDUCTION_MAX)
        top_diameter = root_diameter - diameter_reduction
        
        # Tree can yield [short, short], [long, long], [short, long], or [long, short]
        tree_type = i % 4
        if tree_type == 0:  # [short, short]
            log1 = {"short": root_diameter}
            log2 = {"short": top_diameter}
        elif tree_type == 1:  # [long, long]
            log1 = {"long": root_diameter}
            log2 = {"long": top_diameter}
        elif tree_type == 2:  # [short, long]
            log1 = {"short": root_diameter}
            log2 = {"long": top_diameter}
        else:  # [long, short]
            log1 = {"long": root_diameter}
            log2 = {"short": top_diameter}
        
        trees.append([log1, log2])
        new_logs.extend([log1, log2])
    
    # Combine existing and new logs
    all_logs = existing_logs + new_logs
    
    # Separate logs by length and sort each group by diameter
    long_logs = sorted([log for log in all_logs if "long" in log], key=get_log_diameter, reverse=True)
    short_logs = sorted([log for log in all_logs if "short" in log], key=get_log_diameter, reverse=True)
    
    # Distribute logs into layers (ensuring 2 longs + 2 shorts per layer)
    layers = []
    for layer_index in range(layers_count):
        # Take 2 long and 2 short logs for this layer
        if len(long_logs) < 2 or len(short_logs) < 2:
            raise ValueError(f"Not enough logs for layer {layer_index + 1}: need 2 long and 2 short")
        
        layer_logs = long_logs[:2] + short_logs[:2]
        long_logs = long_logs[2:]
        short_logs = short_logs[2:]
        
        layers.append(layer_logs)
    
    # Sort layers by average diameter (thickest at bottom)
    layers.sort(key=lambda layer: sum(get_log_diameter(log) for log in layer) / len(layer), reverse=True)
    
    # Calculate total cabin height (sum of layer heights - one diameter per layer)
    total_height = sum(get_log_diameter(layer[0]) for layer in layers)  # Use first log of each layer as representative
    
    summary = {
        "trees_to_cut": trees_to_cut,
        "total_height": total_height
    }
    
    return trees, layers, summary

def format_log_display(log):
    """Format a log for display"""
    length = list(log.keys())[0]
    diameter = list(log.values())[0]
    if length == 'long':
        return f"long:  {diameter}"
    else:
        return f"short: {diameter}"

# Database functions
def init_db():
    """Initialize the database and create tables if they don't exist"""
    conn = sqlite3.connect("app.db", check_same_thread=False)
    conn.execute("CREATE TABLE IF NOT EXISTS existing_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, log_data TEXT)")
    conn.commit()
    return conn

def save_logs_to_db(logs):
    """Save logs list to database"""
    conn = init_db()
    conn.execute("DELETE FROM existing_logs")
    for log in logs:
        log_json = json.dumps(log)
        conn.execute("INSERT INTO existing_logs (log_data) VALUES (?)", (log_json,))
    conn.commit()
    conn.close()

def load_logs_from_db():
    """Load logs from database"""
    conn = init_db()
    cur = conn.execute("SELECT log_data FROM existing_logs")
    rows = cur.fetchall()
    conn.close()
    
    logs = []
    for row in rows:
        try:
            log = json.loads(row[0])
            logs.append(log)
        except json.JSONDecodeError:
            continue
    return logs

def add_log_to_db(log):
    """Add a single log to database"""
    logs = load_logs_from_db()
    logs.append(log)
    save_logs_to_db(logs)

def delete_log_from_db(index):
    """Delete log at specific index"""
    logs = load_logs_from_db()
    if 0 <= index < len(logs):
        logs.pop(index)
        save_logs_to_db(logs)

def clear_logs_in_db():
    """Clear all logs from database"""
    conn = init_db()
    conn.execute("DELETE FROM existing_logs")
    conn.commit()
    conn.close()

# Streamlit App
def main():
    st.set_page_config(page_title="Log Optimizer", page_icon="🏠", layout="wide")
    st.title("Log Optimizer")
    st.markdown("**Helps planning a log cabin by optimizing what trees to cut, how to cut them, and how to arrange each course!**")

    # Initialize database
    init_db()
    
    # Sidebar for input
    with st.sidebar:
        st.header("Configuration")
        layers_count = st.number_input("Number of courses", min_value=1, max_value=20, value=9, step=1)
        
        # Root log diameters input
        st.subheader("Available tree sizes")
        diameter_input = st.text_input(
            "Root log center diameters with bark in mm, comma-separated)",
            value="290, 280, 270",
            help="Enter the available root log center diameters with bark in mm, comma-separated"
        )
        
        try:
            root_log_diameters = [int(d.strip()) for d in diameter_input.split(',') if d.strip()]
            if not root_log_diameters:
                st.error("❌ Please enter at least one diameter")
                root_log_diameters = [290, 280, 270]  # fallback
            elif any(d < 100 or d > 500 for d in root_log_diameters):
                st.warning("⚠️ Some diameters seem unusual (should be 100-500mm)")
        except ValueError:
            st.error("❌ Invalid format. Use numbers separated by commas (e.g., 290, 280, 270)")
            root_log_diameters = [290, 280, 270]  # fallback
        
        st.divider()
        
        st.header("Add Existing Logs")
        
        # Method selection
        input_method = st.radio(
            "Choose input method:",
            ["Simple Form", "JSON Input", "Quick Add"]
        )
        
        existing_logs = []
        
        if input_method == "Simple Form":
            st.subheader("Add logs one by one:")
            
            # Load current logs from database
            current_logs = load_logs_from_db()
            
            # Add new log
            col1, col2 = st.columns(2)
            with col1:
                log_type = st.radio("Type", ["long", "short"])
            with col2:
                diameter = st.number_input("Diameter (mm)", min_value=100, max_value=400, value=270, step=10)
            
            if st.button("➕ Add Log"):
                add_log_to_db({log_type: diameter})
                st.rerun()
            
            # Show current logs
            if current_logs:
                st.subheader("Current logs:")
                for i, log in enumerate(current_logs):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"{format_log_display(log)}")
                    with col2:
                        if st.button("🗑️", key=f"del_{i}"):
                            delete_log_from_db(i)
                            st.rerun()
                            
                if st.button("🗑️ Clear All"):
                    clear_logs_in_db()
                    st.rerun()
            
            existing_logs = current_logs
            
        elif input_method == "Quick Add":
            st.subheader("Quick presets:")
            
            if st.button("📦 Small starter (3 logs)"):
                preset_logs = [
                    {"long": 270},
                    {"short": 280}, 
                    {"long": 240}
                ]
                save_logs_to_db(preset_logs)
                st.rerun()
                
            if st.button("📦 Medium set (8 logs)"):
                preset_logs = [
                    {"long": 280}, {"long": 280}, {"long": 270}, {"long": 270},
                    {"short": 280}, {"short": 270}, {"short": 260}, {"short": 250}
                ]
                save_logs_to_db(preset_logs)
                st.rerun()
                
            if st.button("📦 Many long logs (9 logs)"):
                preset_logs = [
                    {"long": 280}, {"long": 280}, {"long": 280}, {"long": 280},
                    {"long": 280}, {"long": 280}, {"long": 280}, {"long": 270},
                    {"short": 280}
                ]
                save_logs_to_db(preset_logs)
                st.rerun()
            
            # Show current logs if any
            current_logs = load_logs_from_db()
            if current_logs:
                existing_logs = current_logs
                st.subheader("Current logs:")
                for log in existing_logs:
                    st.write(f"• {format_log_display(log)}")
            else:
                existing_logs = []
        else:  # JSON Input
            st.subheader("Paste JSON format:")
            
            # Load current logs to populate the text area
            current_logs = load_logs_from_db()
            default_value = json.dumps(current_logs) if current_logs else '[{"long": 270}, {"short": 280}, {"long": 240}]'
            
            json_input = st.text_area(
                "Logs (JSON)",
                value=default_value,
                height=100
            )
            
            try:
                parsed_logs = json.loads(json_input)
                existing_logs = parsed_logs
                st.success(f"✅ {len(existing_logs)} logs loaded")
                
                # Auto-save to database when JSON changes
                if json_input != default_value:
                    save_logs_to_db(existing_logs)
                    
            except json.JSONDecodeError:
                st.error("❌ Invalid JSON format")
                existing_logs = current_logs  # Fall back to current logs
    
    # Main content area
    col1, col2 = st.columns([2, 1], gap="medium")
    
    with col2:
        st.subheader("Existing Logs")
        
        if existing_logs:
            # Sort and display existing logs
            existing_flat = flatten_logs(existing_logs)
            existing_sorted = sorted(existing_flat, key=lambda x: x["diameter"], reverse=False)
            
            long_count = len([l for l in existing_logs if "long" in l])
            short_count = len([l for l in existing_logs if "short" in l])
            
            st.metric("Total logs", len(existing_logs))
            col2_1, col2_2 = st.columns(2)
            with col2_1:
                st.metric("Long logs", long_count)
            with col2_2:
                st.metric("Short logs", short_count)
            
            # Show sorted logs
            st.subheader("Sorted by diameter:")
            for log in existing_sorted:
                if log['length'] == 'long':
                    st.write(f"🪵 **long: {log['diameter']}**")
                else:
                    st.write(f"🪵 **short: {log['diameter']}**")
        else:
            st.info("No existing logs yet")
            st.write("👈 Add logs using the sidebar or optimize with 0 existing logs")
    
    with col1:
        if existing_logs:
            button_text = "🚀 **OPTIMIZE LOGS**"
        else:
            button_text = "🚀 **PLAN FROM SCRATCH**"
            
        if st.button(button_text, type="primary", use_container_width=False):
            try:
                with st.spinner("Optimizing your logs..."):
                    trees, layers, summary = optimize_logs(existing_logs, layers_count, root_log_diameters)
                    
                    result = {
                        "trees_to_cut": summary["trees_to_cut"],
                        "trees": trees,
                        "layers": layers,
                        "total_height_mm": round(summary["total_height"], 1),
                    }
                
                # Display results
                st.success("✅ Optimization complete!")
                
                # Summary metrics
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    st.metric("🌲 Trees to cut", result["trees_to_cut"])
                with col_m2:
                    st.metric("📏 Total height", f"{result['total_height_mm']} mm")
                with col_m3:
                    st.metric("🏗️ Total courses", len(result["layers"]))
                
                # Trees to cut
                with st.expander("🌲 **Trees to Cut**", expanded=True):
                    for i, tree in enumerate(result["trees"], 1):
                        formatted_logs = []
                        for log in tree:
                            length = list(log.keys())[0]
                            diameter = list(log.values())[0]
                            if length == 'long':
                                formatted_logs.append(f"long: {diameter}")
                            else:
                                formatted_logs.append(f"short: {diameter}")
                        log_info = ", ".join(formatted_logs)
                        st.write(f"**Tree {i:2}:** [{log_info}]")
                
                # Layers
                with st.expander("🏗️ **Courses (bottom → top)**", expanded=True):
                    for i, layer in enumerate(result["layers"], 1):
                        formatted_logs = []
                        diameters = []
                        for log in layer:
                            length = list(log.keys())[0]
                            diameter = list(log.values())[0]
                            diameters.append(diameter)
                            if length == 'long':
                                formatted_logs.append(f"long: {diameter}")
                            else:
                                formatted_logs.append(f"short: {diameter}")
                        
                        log_info = ", ".join(formatted_logs)
                        variation = max(diameters) - min(diameters)
                        avg_diameter = sum(diameters) / len(diameters)
                        
                        # Color code based on variation
                        if variation <= 10:
                            icon = "🟢"
                        elif variation <= 20:
                            icon = "🟡"
                        else:
                            icon = "🔴"
                            
                        st.write(f"**Course {i:2}:** [{log_info}] {icon} (avg: {avg_diameter:.0f}mm, variation: {variation}mm)")
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

        # Show example/instructions
        if not existing_logs:
            st.subheader("How it works:")
            st.markdown("""
            1. **Add your existing logs** using the sidebar (any combination of long/short logs)
            2. **Or click "Plan from Scratch"** to get a complete cutting plan  
            3. **View results** showing exactly which trees to cut and how to arrange courses
            
            **The optimizer will:**
            - ✅ Minimize the number of trees you need to cut
            - ✅ Ensure each course has exactly 2 long + 2 short logs  
            - ✅ Create flat, even courses by matching similar diameters
            - ✅ Arrange courses with thickest at bottom, thinnest at top
            """)

if __name__ == "__main__":
    main()