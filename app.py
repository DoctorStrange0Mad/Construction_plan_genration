import streamlit as st
import os
import requests
from io import BytesIO
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import random
# pip install groq
from groq import Groq

try:
    import PyPDF2
except ImportError:
    pass

try:
    import faiss
    import numpy as np
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

# ==========================================
# SYSTEM SETUP & CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="AI House Planner", 
    page_icon="🏗️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# ENGINEERING LOGIC (CORE SYSTEM)
# ==========================================
def calculate_plan(length, width, budget, location, soil, floors):
    area = length * width
    budget_per_sqft = budget / max((area * floors), 1)
    
    is_premium = budget_per_sqft > 2200
    is_economy = budget_per_sqft < 1800
    
    usable_area = area * 0.8
    total_area_all_floors = area * floors
    
    if total_area_all_floors < 800:
        bhk, bed_count, bath_count = "1BHK", 1, 1
    elif total_area_all_floors <= 1500:
        bhk, bed_count, bath_count = "2BHK", 2, 2
    elif total_area_all_floors <= 3000:
        bhk, bed_count, bath_count = "3BHK", 3, 3
    else:
        num_beds = min(floors + 2, 6)
        bhk, bed_count, bath_count = f"{num_beds}BHK", num_beds, num_beds

    variants = []
    base_scale = 1.25 if is_premium else (0.85 if is_economy else 1.0)
    
    profiles = [
        {"name": "Option A - Open plan bias", "living_scale": 1.5, "bed_scale": 0.7, "kitchen_scale": 1.3},
        {"name": "Option B - Bedroom-forward bias", "living_scale": 0.8, "bed_scale": 1.5, "kitchen_scale": 0.8},
        {"name": "Option C - Balanced compact bias", "living_scale": 1.0, "bed_scale": 1.0, "kitchen_scale": 1.0}
    ]
    
    for prof in profiles:
        living = min(max(usable_area * 0.3 * base_scale * prof["living_scale"], 120), 400)
        kitchen = min(max(usable_area * 0.15 * base_scale * prof["kitchen_scale"], 70), 150)
        bed_area = min(max(usable_area * 0.25 * base_scale * prof["bed_scale"], 100), 300)
        bath_area = min(max(usable_area * 0.08 * base_scale, 40), 100)
        
        floors_data = {}
        beds_assigned = 0
        baths_assigned = 0
        
        for f in range(1, floors + 1):
            f_rooms = {}
            if f == 1:
                f_rooms["Living Room"] = round(living, 2)
                f_rooms["Kitchen"] = round(kitchen, 2)
                if is_premium:
                    f_rooms["Dining Room"] = round(living * 0.6, 2)
                    f_rooms["Foyer"] = round(usable_area * 0.05, 2)
                if bed_count > 1 or floors == 1:
                    f_rooms["Guest Bedroom"] = round(bed_area, 2)
                    beds_assigned += 1
                f_rooms["Common Bath"] = round(bath_area, 2)
                baths_assigned += 1
            else:
                if f == floors and is_premium:
                    f_rooms["Master Suite"] = round(bed_area * 1.5, 2)
                    f_rooms["Walk-in Closet"] = round(bed_area * 0.4, 2)
                    f_rooms["Master Bath"] = round(bath_area * 1.5, 2)
                    f_rooms["Balcony"] = round(usable_area * 0.15, 2)
                    beds_assigned += 1
                    baths_assigned += 1
                
                beds_this_floor = max(1, (bed_count - beds_assigned) // max((floors - f + 1), 1))
                if f == floors and beds_this_floor == 0 and bed_count > beds_assigned:
                    beds_this_floor = bed_count - beds_assigned
                    
                for b in range(beds_this_floor):
                    beds_assigned += 1
                    f_rooms[f"Bedroom {beds_assigned}"] = round(bed_area, 2)
                    if baths_assigned < bath_count:
                        baths_assigned += 1
                        f_rooms[f"Attached Bath {baths_assigned}"] = round(bath_area, 2)
                        
                if is_premium and f == 2:
                    f_rooms["Family Lounge"] = round(living * 0.7, 2)
                elif is_premium and f == floors and floors > 2:
                    f_rooms["Home Gym"] = round(bed_area, 2)
                    
            floors_data[f] = f_rooms
            
        variants.append({
            "name": prof["name"],
            "floors_data": floors_data
        })

    foundations = {
        "Clay": "Pile foundation",
        "Sandy": "Raft foundation",
        "Rocky": "Shallow foundation",
        "Loamy": "Combined footing"
    }
    foundation = foundations.get(soil, "RCC standard")

    loc_lower = location.lower()
    insights = []
    if any(k in loc_lower for k in ["coastal", "kerala"]):
        insights.append("High rainfall zone → Recommend superior waterproofing & sloped roofs.")
    if any(k in loc_lower for k in ["delhi", "north"]):
        insights.append("Temperature extremes → Recommend thermal insulation & double-glazed windows.")
    if "himalaya" in loc_lower:
        insights.append("Seismic risk → Recommend earthquake-resistant structural design.")
        
    if is_premium:
        insights.append("🌟 Premium Budget Detected → Integrating luxury layouts (Walk-in closets, Balconies).")
    elif is_economy:
        insights.append("💡 Economy Budget Detected → Optimizing space strictly for utility.")

    super_built_up = int(total_area_all_floors)
    circulation = int(super_built_up * 0.25)

    return {
        "area": area,
        "super_built_up": super_built_up,
        "circulation": circulation,
        "bhk": bhk,
        "variants": variants,
        "foundation": foundation,
        "insights": insights
    }

def estimate_cost(area, budget, location, floors):
    base_rate = 2000
    sqft_allowance = budget / max((area * floors), 1)
    
    if sqft_allowance < 1800:
        base_rate = 1500
    elif sqft_allowance > 2200:
        base_rate = 2500
        
    loc_lower = location.lower()
    if any(k in loc_lower for k in ["mumbai", "delhi", "bangalore"]):
        base_rate = min(base_rate + 300, 2500)
        
    total_cost = area * base_rate * floors
    
    return {
        "cost_per_sqft": base_rate,
        "total_cost": total_cost,
        "materials": total_cost * 0.60,
        "labor": total_cost * 0.30,
        "misc": total_cost * 0.10,
        "surplus": budget - total_cost
    }

# ==========================================
# AI INTEGRATION (GROQ)
# ==========================================
def generate_ai_response(plan, cost_data, pdf_context=""):
    try:
        api_key = st.secrets.get("GROQ_API_KEY")
        if api_key == "paste_your_actual_groq_api_key_here":
            api_key = None
    except Exception:
        api_key = None
        
    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        return "⚠️ **GROQ_API_KEY** not properly configured! Please paste your key into the `./.streamlit/secrets.toml` file to run AI Insights."
        
    try:
        prompt = f"""
        Act as a professional architect. Review this house plan:
        Layout: {plan['bhk']}, {plan['area']} sqft per floor ({len(plan['floors_data'])} floors total)
        Floor Layouts: {plan['floors_data']}
        Foundation: {plan['foundation']} Based on soil.
        Site Insights: {', '.join(plan['insights']) if plan['insights'] else 'Standard conditions'}
        Cost: ₹{cost_data['total_cost']} (Materials: 60%, Labor: 30%, Misc: 10%)
        
        Additional PDF Document Context (if any): {pdf_context}
        
        Provide a detailed architectural floor plan description formatted EXACTLY like this:
        FLOOR 1:
        * Room layout with positions (e.g. Kitchen at front-left, Living room at front-right)
        * Staircase position explicitly stated and flow
        
        FLOOR 2 (if exists):
        * Changes from ground floor
        * Bedroom and Bathroom positions aligned
        
        Finally, Provide:
        1. Review of structural feasibility (especially vertical alignment of stairs).
        2. Suggestions to optimize ventilation and lighting.
        """
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a professional architect specializing in residential floor plan analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1024,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"⚠️ **AI generation failed.** Error: {str(e)}"

# ==========================================
# 2D CAD FLOOR PLAN VISUALIZATION
# ==========================================
def generate_2d_floor_plan(length, width, floor_rooms, floor_num, total_floors, theme="dark", variant_name=""):
    fig, ax = plt.subplots(figsize=(10, 10 * (length / width)))
    
    if theme == "dark":
        bg_color = '#0e1117'
        wall_color, room_fill, text_color = '#ffffff', '#1E1E2E', '#00ffff'
        dim_color, door_color = '#ffff00', '#ff00ff'
        hatch_color = '#555555'
    else:
        bg_color = '#ffffff'
        wall_color, room_fill, text_color = '#000000', '#f9f9f9', '#000000'
        dim_color, door_color = '#d32f2f', '#ff0000'
        hatch_color = '#888888'
        
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    
    # Masonry setup
    thickness = 0.75
    ax.add_patch(patches.Rectangle((0, 0), width, length, linewidth=2, edgecolor=wall_color, facecolor='none', zorder=5))
    ax.add_patch(patches.Rectangle((thickness, thickness), width-2*thickness, length-2*thickness, linewidth=2, edgecolor=wall_color, facecolor='none', zorder=5))
    
    walls = [
        patches.Rectangle((0, 0), width, thickness, edgecolor=hatch_color, facecolor=bg_color, hatch='////', zorder=4),
        patches.Rectangle((0, length-thickness), width, thickness, edgecolor=hatch_color, facecolor=bg_color, hatch='////', zorder=4),
        patches.Rectangle((0, thickness), thickness, length-2*thickness, edgecolor=hatch_color, facecolor=bg_color, hatch='////', zorder=4),
        patches.Rectangle((width-thickness, thickness), thickness, length-2*thickness, edgecolor=hatch_color, facecolor=bg_color, hatch='////', zorder=4),
    ]
    for w in walls: ax.add_patch(w)
    ax.add_patch(patches.Rectangle((thickness, thickness), width-2*thickness, length-2*thickness, edgecolor=hatch_color, facecolor=bg_color, hatch='////', zorder=1))
    
    rooms = {k: float(v) for k,v in floor_rooms.items() if float(v) > 0}
    if not rooms: return fig
    
    v_name = variant_name.lower()
    is_wide = width > length
    is_option_c = 'option c' in v_name or 'balanced' in v_name
    is_option_b = 'option b' in v_name or 'bedroom' in v_name
    
    grp_front = ['foyer', 'living', 'kitchen', 'dining', 'porch']
    grp_mid = ['staircase', 'bath', 'open space', 'walk', 'lounge', 'family']
    grp_rear = ['bedroom', 'balcony', 'gym', 'master']
    
    rooms_1, rooms_2, rooms_3 = [], [], []
    for nm, ar in rooms.items():
        n = nm.lower()
        if is_option_b:
            if any(x in n for x in grp_rear): rooms_1.append({"name": nm, "area": ar})
            elif any(x in n for x in grp_mid): rooms_2.append({"name": nm, "area": ar})
            else: rooms_3.append({"name": nm, "area": ar})
        elif is_option_c:
            if any(x in n for x in grp_front): rooms_1.append({"name": nm, "area": ar})
            elif 'corridor' in n or any(x in n for x in grp_mid): rooms_2.append({"name": nm, "area": ar})
            else: rooms_3.append({"name": nm, "area": ar})
        else:
            if any(x in n for x in grp_front): rooms_1.append({"name": nm, "area": ar})
            elif any(x in n for x in grp_mid): rooms_2.append({"name": nm, "area": ar})
            else: rooms_3.append({"name": nm, "area": ar})
            
    groups = [g for g in [rooms_1, rooms_2, rooms_3] if g]
    t_all = sum(r['area'] for g in groups for r in g)
    
    def slice_rect(r_tuple, g_rooms, vertical=True):
        r_x, r_y, r_w, r_h = r_tuple
        t_a = sum(rr['area'] for rr in g_rooms)
        if t_a <= 0: return []
        res, c_x, c_y = [], r_x, r_y
        for rr in g_rooms:
            ratio = rr['area'] / t_a
            if vertical:
                sw = r_w * ratio
                res.append({"name": rr['name'], "rect": (c_x, r_y, sw, r_h), "area": rr['area']})
                c_x += sw
            else:
                sh = r_h * ratio
                res.append({"name": rr['name'], "rect": (r_x, c_y, r_w, sh), "area": rr['area']})
                c_y += sh
        return res
        
    all_rooms = []
    irx, iry, irw, irh = thickness, thickness, width - 2*thickness, length - 2*thickness
    
    if is_option_c:
        cx = irx
        for grp in groups:
            ga = sum(r['area'] for r in grp)
            gw = irw * (ga / t_all)
            all_rooms.extend(slice_rect((cx, iry, gw, irh), grp, vertical=False))
            cx += gw
    else:
        if is_wide:
            cx = irx
            for grp in groups:
                ga = sum(r['area'] for r in grp)
                gw = irw * (ga / t_all)
                all_rooms.extend(slice_rect((cx, iry, gw, irh), grp, vertical=False))
                cx += gw
        else:
            cy = iry
            for grp in groups:
                ga = sum(r['area'] for r in grp)
                gh = irh * (ga / t_all)
                all_rooms.extend(slice_rect((irx, cy, irw, gh), grp, vertical=True))
                cy += gh
                
    def ft_in(val):
        ft = int(val)
        ins = int(round((val - ft) * 12))
        if ins == 12: ft, ins = ft+1, 0
        return f"{ft}'{ins}\""

    for rm in all_rooms:
        rn, nl = rm['name'], rm['name'].lower()
        rx, ry, rw, rh = rm['rect']
        
        gap = 0.25
        dx, dy = rx + gap, ry + gap
        w_gap, h_gap = max(0.1, rw - 2*gap), max(0.1, rh - 2*gap)
        
        rp = patches.Rectangle((dx, dy), w_gap, h_gap, edgecolor=wall_color, facecolor=room_fill, linewidth=1.5, zorder=2)
        ax.add_patch(rp)
        
        door_w = 2.5 if "bath" in nl else 3.0
        placed_door = False
        
        if any(x in nl for x in ['foyer', 'living', 'porch']) and dy <= 1.0:
            door_cut = patches.Rectangle((dx + 0.5, 0), door_w, 1.0, facecolor=room_fill, edgecolor='none', zorder=3)
            ax.add_patch(door_cut)
            ax.plot([dx + 0.5, dx + 0.5], [1.0, 1.0 + door_w], color=door_color, linewidth=1.5, zorder=4)
            ax.add_patch(patches.Arc((dx + 0.5, 1.0), door_w*2, door_w*2, theta1=0, theta2=90, color=door_color, linewidth=1.5, zorder=4))
            placed_door = True
            
        if not placed_door and "open space" not in nl and "balcony" not in nl:
            if ry > 1.0 and w_gap > door_w + 1:
                door_cut = patches.Rectangle((dx + 0.5, dy - 2*gap), door_w, 2*gap, facecolor=room_fill, edgecolor='none', zorder=3)
                ax.add_patch(door_cut)
                ax.plot([dx + 0.5, dx + 0.5 + door_w], [dy, dy + door_w], color=door_color, lw=1.5, zorder=4)
                ax.add_patch(patches.Arc((dx + 0.5, dy), door_w*2, door_w*2, theta1=0, theta2=90, color=door_color, lw=1.5, zorder=4))
            elif rx > 1.0 and h_gap > door_w + 1:
                door_cut = patches.Rectangle((dx - 2*gap, dy + 0.5), 2*gap, door_w, facecolor=room_fill, edgecolor='none', zorder=3)
                ax.add_patch(door_cut)
                ax.plot([dx, dx + door_w], [dy + 0.5, dy + 0.5], color=door_color, lw=1.5, zorder=4)
                ax.add_patch(patches.Arc((dx, dy + 0.5), door_w*2, door_w*2, theta1=0, theta2=90, color=door_color, lw=1.5, zorder=4))
            elif ry + rh < length - 1.0 and w_gap > door_w + 1:
                door_cut = patches.Rectangle((dx + 0.5, dy + h_gap), door_w, 2*gap, facecolor=room_fill, edgecolor='none', zorder=3)
                ax.add_patch(door_cut)
                ax.plot([dx + 0.5, dx + 0.5 + door_w], [dy + h_gap, dy + h_gap - door_w], color=door_color, lw=1.5, zorder=4)
                ax.add_patch(patches.Arc((dx + 0.5, dy + h_gap), door_w*2, door_w*2, theta1=270, theta2=360, color=door_color, lw=1.5, zorder=4))
                
        win_span = min(4.0, w_gap*0.4) if (rw > rh) else min(4.0, h_gap*0.4)
        if "bath" not in nl and "stair" not in nl and "corridor" not in nl:
            if dy <= 1.0 and w_gap > win_span:
                bx, by = dx + w_gap/2 - win_span/2, 0
                ax.add_patch(patches.Rectangle((bx, by), win_span, 0.75, facecolor=room_fill, edgecolor='none', zorder=3))
                for off in [0, 0.375, 0.75]: ax.plot([bx, bx+win_span], [by+off, by+off], color=dim_color, lw=1.5, zorder=4)
            elif dx <= 1.0 and h_gap > win_span:
                bx, by = 0, dy + h_gap/2 - win_span/2
                ax.add_patch(patches.Rectangle((bx, by), 0.75, win_span, facecolor=room_fill, edgecolor='none', zorder=3))
                for off in [0, 0.375, 0.75]: ax.plot([bx+off, bx+off], [by, by+win_span], color=dim_color, lw=1.5, zorder=4)
            elif dy + h_gap >= length - 1.0 and w_gap > win_span:
                bx, by = dx + w_gap/2 - win_span/2, length-0.75
                ax.add_patch(patches.Rectangle((bx, by), win_span, 0.75, facecolor=room_fill, edgecolor='none', zorder=3))
                for off in [0, 0.375, 0.75]: ax.plot([bx, bx+win_span], [by+off, by+off], color=dim_color, lw=1.5, zorder=4)
            elif dx + w_gap >= width - 1.0 and h_gap > win_span:
                bx, by = width-0.75, dy + h_gap/2 - win_span/2
                ax.add_patch(patches.Rectangle((bx, by), 0.75, win_span, facecolor=room_fill, edgecolor='none', zorder=3))
                for off in [0, 0.375, 0.75]: ax.plot([bx+off, bx+off], [by, by+win_span], color=dim_color, lw=1.5, zorder=4)

        fsz = max(min(w_gap, h_gap) * 0.8, 4)
        fsz = min(fsz, 14)
        ax.text(dx + w_gap/2, dy + h_gap/2, f"{rn.upper()}\n{ft_in(rw)} x {ft_in(rh)}", color=text_color, fontsize=fsz, fontweight='bold', ha='center', va='center', zorder=5)

    ax.annotate('', xy=(0, length+2), xytext=(width, length+2), arrowprops=dict(arrowstyle='<|-|>', color=dim_color, lw=1.5))
    ax.text(width/2, length+2.5, f"{int(width)}'", color=text_color, ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    ax.annotate('', xy=(-3, 0), xytext=(-3, length), arrowprops=dict(arrowstyle='<|-|>', color=dim_color, lw=1.5))
    ax.text(-3.5, length/2, f"{int(length)}'", color=text_color, ha='right', va='center', rotation=90, fontsize=12, fontweight='bold')
    
    N_x, N_y = width - 4, length + 4
    ax.plot([N_x, N_x], [N_y, N_y+3], color=text_color, lw=2, zorder=5)
    ax.plot([N_x-1, N_x, N_x+1], [N_y+2, N_y+3, N_y+2], color=text_color, lw=2, zorder=5)
    ax.text(N_x, N_y+3.5, "N", color=text_color, ha='center', va='bottom', fontweight='bold', fontsize=14, zorder=5)

    ax.text(0, length + 7, f"PLOT: {int(width)}x{int(length)} | {variant_name.upper()}", color=text_color, fontsize=16, fontweight='bold', ha='left')
    floor_label = "GROUND FLOOR" if floor_num == 1 else f"FLOOR {floor_num}"
    ax.text(0, length + 5, f"{floor_label} PLAN | SQ.FT: {int(width * length * total_floors)}", color=text_color, fontsize=12, ha='left')

    ax.set_xlim(-width * 0.15, width * 1.05)
    ax.set_ylim(-length * 0.05, length * 1.25)
    ax.set_aspect('equal')
    ax.axis('off')
    
    return fig

# ==========================================
# PDF & FAISS INTEGRATION
# ==========================================
def extract_pdf_text(uploaded_file):
    if 'PyPDF2' not in globals():
        return ""
    try:
        reader = PyPDF2.PdfReader(uploaded_file)
        text = "".join(page.extract_text() + "\n" for page in reader.pages)
        return text
    except Exception:
        return ""

def create_faiss_index(text):
    if not HAS_FAISS or not text.strip():
        return None, []
        
    chunks = [c for c in text.split('\n\n') if len(c.strip()) > 30]
    if not chunks:
        return None, []

    # Fallback to simple TF-IDF or random projection if sentence_transformers isn't available
    # to avoid heavy ML model loading in a simple script layout, we mock the embedding dimensionality
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
        embeddings = model.encode(chunks)
        
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(np.array(embeddings).astype("float32"))
        return index, chunks, model
    except ImportError:
        return None, chunks

def search_index(query, index_data):
    if not HAS_FAISS:
        return ""
        
    index, chunks, *model_container = index_data if isinstance(index_data, tuple) else (None, [], None)
    if not index or not chunks:
        # Simple keyword search fallback if FAISS index failed to build fully
        keywords = query.lower().split()
        results = [c for c in (chunks or []) if any(k in c.lower() for k in keywords)]
        return "\n".join(results[:3])
        
    try:
        model = model_container[0]
        query_vector = model.encode([query])
        D, I = index.search(np.array(query_vector).astype("float32"), k=min(2, len(chunks)))
        
        return "\n".join(chunks[i] for i in I[0] if i < len(chunks))
    except Exception:
        return ""

# ==========================================
# STREAMLIT UI/UX DESIGN
# ==========================================
def main():
    st.title("🏗️ AI House Planner & Intelligent Construction Assistant")
    st.markdown("---")

    # SIDEBAR INPUTS
    st.sidebar.header("🧾 Project Requirements")
    length = st.sidebar.number_input("Plot Length (feet)", min_value=10.0, max_value=1000.0, value=40.0, step=1.0)
    width = st.sidebar.number_input("Plot Width (feet)", min_value=10.0, max_value=1000.0, value=30.0, step=1.0)
    budget = st.sidebar.number_input("Budget (INR)", min_value=100000, max_value=100000000, value=2500000, step=100000)
    location = st.sidebar.text_input("Location", value="Mumbai")
    soil = st.sidebar.selectbox("Soil Type", ["Clay", "Sandy", "Loamy", "Rocky", "Unknown"])
    floors = st.sidebar.number_input("Number of Floors", min_value=1, max_value=10, value=1, step=1)
    
    st.sidebar.markdown("---")
    blueprint_theme = st.sidebar.radio("Blueprint Theme", ["Dark Mode", "Light Mode"])
    theme_val = "dark" if blueprint_theme == "Dark Mode" else "light"
    
    pdf_file = st.sidebar.file_uploader("Upload Guidelines/Codes (PDF) [Optional]", type=["pdf"])

    if st.sidebar.button("Generate Plan", type="primary", use_container_width=True):
        if budget < 100000:
            st.sidebar.error("Budget must be at least ₹1 Lakh")
            st.stop()
        if length <= 0 or width <= 0:
            st.sidebar.error("Dimensions must be positive values.")
            st.stop()
            
        # Core Computation
        with st.spinner("Calculating engineering specs..."):
            plan = calculate_plan(length, width, budget, location, soil, floors)
            cost = estimate_cost(plan['area'], budget, location, floors)
            
        pdf_context = ""
        if pdf_file:
            with st.spinner("Processing PDF Document..."):
                pdf_text = extract_pdf_text(pdf_file)
                if HAS_FAISS:
                    index_data = create_faiss_index(pdf_text)
                    pdf_context = search_index("construction layout foundation material", index_data)
                else:
                    pdf_context = pdf_text[:1000] # Fallback without FAISS

        # Store to session_state
        st.session_state.plan_meta = {
            "area": plan["area"],
            "super_built_up": plan["super_built_up"],
            "circulation": plan["circulation"],
            "bhk": plan["bhk"],
            "foundation": plan["foundation"],
            "insights": plan["insights"]
        }
        st.session_state.variants = plan["variants"]
        st.session_state.cost = cost
        st.session_state.pdf_context = pdf_context
        st.session_state.active_variant_idx = 0
        st.session_state.ai_insights = None

    if "variants" in st.session_state:
        # Variant Selection
        variant_names = [v["name"] for v in st.session_state.variants]
        st.markdown("### 🏘️ Layout Variants")
        selected_variant_name = st.radio("Select a design profile:", variant_names, index=st.session_state.active_variant_idx, horizontal=True)
        st.session_state.active_variant_idx = variant_names.index(selected_variant_name)
        
        active_idx = st.session_state.active_variant_idx
        active_variant = st.session_state.variants[active_idx]
        floors_data = active_variant["floors_data"]
        
        live_area = length * width
        live_super_built_up = int(live_area * floors)
        live_circulation = int(live_super_built_up * 0.25)
        live_cost = estimate_cost(live_area, budget, location, floors)
        
        plan_meta = st.session_state.plan_meta
        pdf_context = st.session_state.pdf_context

        # Display Structured Outputs
        col1, col2 = st.columns([1, 1], gap="large")
        
        with col1:
            st.subheader("📐 House Summary")
            st.metric("Total Plot Area (Ground)", f"{live_area} sq.ft")
            st.metric("Super Built-up Area Total", f"{live_super_built_up} sq.ft")
            st.metric("Estimated Wall & Circulation Base", f"{live_circulation} sq.ft")
            st.metric("Recommended Unit", plan_meta['bhk'])
            
            with st.expander("🏠 Room Layout Details", expanded=True):
                for f_num, f_rooms in floors_data.items():
                    st.markdown(f"**Floor {f_num} Layout:**")
                    for room, size in f_rooms.items():
                        st.markdown(f"- **{room}**: `{size} sq.ft`")
                    st.write("")
                
            with st.expander("🏗️ Structural Plan", expanded=True):
                st.markdown(f"**Foundation Type:** `{plan_meta['foundation']}`")
                for ins in plan_meta['insights']:
                    st.info(ins)

        with col2:
            st.subheader("💰 Cost Breakdown")
            st.metric("Total Estimated Cost", f"₹{live_cost['total_cost']:,}")
            st.metric("Estimated Cost per sq.ft", f"₹{live_cost['cost_per_sqft']:,}")
            
            st.write("**Budget Allocation**")
            st.progress(0.60, text=f"Materials (60%): ₹{int(live_cost['materials']):,}")
            st.progress(0.30, text=f"Labor (30%): ₹{int(live_cost['labor']):,}")
            st.progress(0.10, text=f"Misc (10%): ₹{int(live_cost['misc']):,}")
            
            st.write("")
            if live_cost['surplus'] >= 0:
                st.success(f"✅ **Within Budget!** Surplus: ₹{live_cost['surplus']:,}")
            else:
                deficit = abs(live_cost['surplus'])
                st.error(f"⚠️ **Over Budget** by ₹{deficit:,}. Consider optimizing space or materials.")

        st.markdown("---")
        
        st.subheader("🛠️ Interactive Room Editor")
        st.markdown("Adjust the sizes of specific rooms below. Changes instantly update the blueprint.")
        
        total_generated_floors = len(floors_data)
        editor_cols = st.columns(total_generated_floors)
        for f_num in sorted(floors_data.keys()):
            col_idx = (f_num - 1) % len(editor_cols)
            with editor_cols[col_idx]:
                st.markdown(f"**Floor {f_num} Rooms**")
                for room_name, current_size in list(floors_data[f_num].items()):
                    slider_key = f"slider_{active_idx}_{f_num}_{room_name}"
                    new_size = st.slider(
                        room_name,
                        min_value=10.0,
                        max_value=float(max(1000.0, current_size * 3)),
                        value=float(current_size),
                        step=5.0,
                        key=slider_key
                    )
                    st.session_state.variants[active_idx]["floors_data"][f_num][room_name] = round(new_size, 2)

        st.markdown("---")
        st.subheader("🎨 House Visualization (2D Blueprint)")
        
        tabs = st.tabs([f"Floor {i}" for i in range(1, total_generated_floors + 1)])
        for i, tab in enumerate(tabs):
            with tab:
                f_num = i + 1
                fig = generate_2d_floor_plan(length, width, floors_data[f_num], f_num, total_generated_floors, theme=theme_val, variant_name=selected_variant_name)
                if fig:
                    st.pyplot(fig)
                else:
                    st.warning(f"Failed to render Floor {f_num}.")

        st.markdown("---")
        # AI & Image Generation Visuals
        st.subheader("🤖 AI Architect Insights")
        
        if st.button("Validate Layout with AI Architect", type="primary"):
            with st.spinner("Consulting AI Architect..."):
                current_plan_data = dict(plan_meta)
                current_plan_data["floors_data"] = floors_data
                ai_insights = generate_ai_response(current_plan_data, live_cost, pdf_context)
                st.session_state.ai_insights = ai_insights
                
        if st.session_state.get("ai_insights"):
            with st.container(border=True):
                st.markdown(st.session_state.ai_insights)
            
            if pdf_context:
                with st.expander("PDF Context Used"):
                    st.text(pdf_context)

if __name__ == "__main__":
    main()
