#!/usr/bin/env python3

import streamlit as st
import json
from typing import List, Dict, Tuple
import math
import sqlite3

# Type definitions
Log = Dict[str, int]  # {"long": diameter} or {"short": diameter}
Tree = List[Log]      # [root_log, top_log]
Layer = List[Log]     # [log1, log2, log3, log4]

# TODO: add långdragsinskning (not bottom layer)
# course alternations?

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

def optimize_logs(existing_logs: List[Log], layers_count: int, root_log_diameters: List[int], 
                 long_length: int, short_length: int, diameter_reduction_per_meter: int, shrinkage_percentage: float, bark_thickness: int, belly_groove_reduction: int, minimum_wall_height: int = None) -> Tuple[List[Tree], List[Layer], Dict]:
    """
    Optimize logs.
    
    Args:
        existing_logs: List of existing logs in format [{"long": 260}, {"short": 210}, ...]
        layers_count: Number of layers (courses) to build (None if using minimum_wall_height)
        root_log_diameters: Available root log diameters for new trees
        long_length: Length of long logs in mm
        short_length: Length of short logs in mm
        diameter_reduction_per_meter: Diameter reduction per meter of tree length
        shrinkage_percentage: Percentage of diameter reduction due to wood shrinkage
        bark_thickness: Thickness of bark to subtract from diameter for wall height calculations
        belly_groove_reduction: Wall height reduction due to belly groove, affects all logs except bottom one
        minimum_wall_height: Minimum desired wall height in mm (None if using layers_count)
    
    Returns:
        Tuple of (trees_to_cut, layers, summary)
    """
    # If minimum wall height is specified, calculate required layers_count
    if minimum_wall_height is not None:
        # Estimate average log height after all reductions
        avg_log_diameter = sum(root_log_diameters) / len(root_log_diameters)
        estimated_first_layer_height = max(0, avg_log_diameter - bark_thickness) * (1 - shrinkage_percentage/100)
        estimated_other_layer_height = max(0, avg_log_diameter - bark_thickness - belly_groove_reduction) * (1 - shrinkage_percentage/100)
        
        # Calculate how many layers we need
        if estimated_other_layer_height <= 0:
            layers_count = 1
        else:
            remaining_height = minimum_wall_height - estimated_first_layer_height
            if remaining_height <= 0:
                layers_count = 1
            else:
                additional_layers = math.ceil(remaining_height / estimated_other_layer_height)
                layers_count = 1 + additional_layers
        
        # Cap at reasonable maximum
        layers_count = min(layers_count, 30)
    
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
        
        # Tree can yield [short, short], [long, long], [short, long], or [long, short]
        tree_type = i % 4
        if tree_type == 0:  # [short, short]
            # First log: middle at short_length/2
            log1_middle_diameter = root_diameter - (short_length/2) * (diameter_reduction_per_meter / 1000)
            # Second log: middle at short_length + short_length/2
            log2_middle_diameter = root_diameter - (short_length + short_length/2) * (diameter_reduction_per_meter / 1000)
            log1 = {"short": int(log1_middle_diameter)}
            log2 = {"short": int(log2_middle_diameter)}
        elif tree_type == 1:  # [long, long]
            # First log: middle at long_length/2
            log1_middle_diameter = root_diameter - (long_length/2) * (diameter_reduction_per_meter / 1000)
            # Second log: middle at long_length + long_length/2
            log2_middle_diameter = root_diameter - (long_length + long_length/2) * (diameter_reduction_per_meter / 1000)
            log1 = {"long": int(log1_middle_diameter)}
            log2 = {"long": int(log2_middle_diameter)}
        elif tree_type == 2:  # [short, long]
            # First log: middle at short_length/2
            log1_middle_diameter = root_diameter - (short_length/2) * (diameter_reduction_per_meter / 1000)
            # Second log: middle at short_length + long_length/2
            log2_middle_diameter = root_diameter - (short_length + long_length/2) * (diameter_reduction_per_meter / 1000)
            log1 = {"short": int(log1_middle_diameter)}
            log2 = {"long": int(log2_middle_diameter)}
        else:  # [long, short]
            # First log: middle at long_length/2
            log1_middle_diameter = root_diameter - (long_length/2) * (diameter_reduction_per_meter / 1000)
            # Second log: middle at long_length + short_length/2
            log2_middle_diameter = root_diameter - (long_length + short_length/2) * (diameter_reduction_per_meter / 1000)
            log1 = {"long": int(log1_middle_diameter)}
            log2 = {"short": int(log2_middle_diameter)}
        
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
    
    # Calculate total cabin height and add accumulated heights after shrinkage
    total_height = 0
    for i, layer in enumerate(layers):
        layer_height = max(0, get_log_diameter(layer[0]) - bark_thickness)  # Subtract bark
        if i > 0:  # Apply belly groove reduction to all layers except the bottom one (index 0)
            layer_height = max(0, layer_height - belly_groove_reduction)
        total_height += layer_height
    
    total_height_after_shrinkage = total_height * (1 - shrinkage_percentage/100)
    
    # Add accumulated height to each layer
    accumulated_height = 0
    for i, layer in enumerate(layers):
        layer_height = max(0, get_log_diameter(layer[0]) - bark_thickness)  # Representative height for this layer, subtract bark
        if i > 0:  # Apply belly groove reduction to all layers except the bottom one (index 0)
            layer_height = max(0, layer_height - belly_groove_reduction)
        layer_height_after_shrinkage = layer_height * (1 - shrinkage_percentage/100)
        accumulated_height += layer_height_after_shrinkage
        # Add accumulated height as metadata to the layer
        layer.append({"_accumulated_height": round(accumulated_height, 1)})
    
    summary = {
        "trees_to_cut": trees_to_cut,
        "total_height": total_height,
        "total_height_after_shrinkage": round(total_height_after_shrinkage, 1)
    }
    
    # If minimum wall height is specified, keep adding layers until requirement is met
    if minimum_wall_height is not None:
        while total_height_after_shrinkage < minimum_wall_height and len(layers) < 30:  # Safety cap
            # Add one more layer with average diameter logs
            avg_diameter = sum(root_log_diameters) / len(root_log_diameters)
            extra_layer = [{"long": int(avg_diameter)}, {"long": int(avg_diameter)}, {"short": int(avg_diameter)}, {"short": int(avg_diameter)}]
            layers.append(extra_layer)
            
            # Calculate height contribution of this extra layer
            extra_layer_height = max(0, avg_diameter - bark_thickness - belly_groove_reduction)  # Apply all reductions
            total_height += extra_layer_height
            total_height_after_shrinkage = total_height * (1 - shrinkage_percentage/100)
            
            # Update trees_to_cut (need 2 more logs = 1 more tree)
            trees_to_cut += 1
            # Add the tree for the extra logs (consistent with original tree structure)
            log1 = {"long": int(avg_diameter)}
            log2 = {"short": int(avg_diameter)}
            trees.append([log1, log2])
        
        # Recalculate accumulated height for all layers after adding extra layers
        accumulated_height = 0
        for i, layer in enumerate(layers):
            # Skip metadata if it exists
            logs_in_layer = [log for log in layer if isinstance(log, dict) and ('long' in log or 'short' in log)]
            if logs_in_layer:
                layer_height = max(0, get_log_diameter(logs_in_layer[0]) - bark_thickness)
                if i > 0:
                    layer_height = max(0, layer_height - belly_groove_reduction)
                layer_height_after_shrinkage = layer_height * (1 - shrinkage_percentage/100)
                accumulated_height += layer_height_after_shrinkage
                
                # Remove existing metadata and add updated accumulated height
                layer[:] = logs_in_layer  # Keep only the log dictionaries
                layer.append({"_accumulated_height": round(accumulated_height, 1)})
        
        # Update summary with final values
        summary = {
            "trees_to_cut": trees_to_cut,
            "total_height": total_height,
            "total_height_after_shrinkage": round(total_height_after_shrinkage, 1)
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
        
        # Choose between courses or minimum height
        build_method = st.radio(
            "Build method:",
            ["Minimum wall height", "Number of courses"]
        )
        
        if build_method == "Minimum wall height":
            minimum_wall_height = st.number_input("Minimum wall height (mm)", min_value=500, max_value=5000, value=1740, step=50)
            layers_count = None
        else:
            layers_count = st.number_input("Number of courses", min_value=1, max_value=20, value=9, step=1)
            minimum_wall_height = None
        
        st.subheader("Log dimensions")
        long_length = st.number_input(
            "Long log length (mm)", 
            min_value=3000, max_value=8000, value=5150, step=50,
            help="Length of long logs in millimeters"
        )
        short_length = st.number_input(
            "Short log length (mm)", 
            min_value=2000, max_value=6000, value=4050, step=50,
            help="Length of short logs in millimeters"
        )
        diameter_reduction_per_meter = st.number_input(
            "Diameter reduction per meter (mm/m)", 
            min_value=5, max_value=20, value=10, step=1,
            help="How many millimeters the tree diameter reduces per meter of length"
        )
        shrinkage_percentage = st.number_input(
            "Wood shrinkage (%)", 
            min_value=0, max_value=20, value=6, step=1,
            help="Percentage of diameter reduction due to wood shrinkage after drying"
        )
        bark_thickness = st.number_input(
            "Bark thickness (mm)", 
            min_value=0, max_value=50, value=20, step=1,
            help="Thickness of bark at root log center, to subtract from diameter for wall height calculations"
        )
        belly_groove_reduction = st.number_input(
            "Belly groove reduction (mm)", 
            min_value=0, max_value=50, value=25, step=1,
            help="Wall height reduction due to cutting of the belly groove, affects all logs except the bottom one"
        )
        
        # Root log diameters input
        st.subheader("Available tree sizes")
        diameter_input = st.text_input(
            "Root log center diameters with bark in mm, comma-separated)",
            value="287",
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
        st.info("💡 Diameters are entered as root log center diameters with bark in mm")
        
        # Method selection
        input_method = st.radio(
            "Choose input method:",
            ["Simple Form", "JSON Input"]
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
                diameter = st.number_input("Diameter (mm)", min_value=100, max_value=400, value=287, step=10)
            
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
            
        else:  # JSON Input
            st.subheader("Paste JSON format:")
            
            # Load current logs to populate the text area
            current_logs = load_logs_from_db()
            default_value = json.dumps(current_logs) if current_logs else '[{"long": 287}, {"short": 287}, {"long": 287}, {"short": 287}]'
            
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
                    trees, layers, summary = optimize_logs(
                        existing_logs, layers_count, root_log_diameters,
                        long_length, short_length, diameter_reduction_per_meter, shrinkage_percentage, bark_thickness, belly_groove_reduction, minimum_wall_height
                    )
                    
                    result = {
                        "trees_to_cut": summary["trees_to_cut"],
                        "trees": trees,
                        "layers": layers,
                        "total_height_mm": round(summary["total_height"], 1),
                        "total_height_after_shrinkage_mm": summary["total_height_after_shrinkage"],
                    }
                
                # Display results
                st.success("✅ Optimization complete!")
                
                # Summary metrics
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    st.metric("🌲 Trees to cut", result["trees_to_cut"])
                with col_m2:
                    st.metric("📏 Wall height after shrinkage", f"{result['total_height_after_shrinkage_mm']} mm")
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
                        accumulated_height = None
                        
                        for log in layer:
                            if isinstance(log, dict) and "_accumulated_height" in log:
                                accumulated_height = log["_accumulated_height"]
                            else:
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
                        
                        height_info = f" | wall height: {accumulated_height}mm" if accumulated_height else ""
                        st.write(f"**Course {i:2}:** [{log_info}] {icon} (avg: {avg_diameter:.0f}mm, variation: {variation}mm{height_info})")
                
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