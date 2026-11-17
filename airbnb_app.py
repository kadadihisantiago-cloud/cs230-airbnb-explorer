"""
Name: Santiago Kadadihi
CS230-7 (online, Prof. Frydenberg)
Data: Inside Airbnb Cambridge MA listings (Sept 2026)
App URL: (to be added after publishing)

Description: This app is for someone visiting Bentley, Harvard or MIT for a
short stay who wants to find a fairly priced Airbnb in a good Cambridge
neighborhood. You can filter listings by room type, neighborhood, budget and
reviews, compare prices across neighborhoods, look at hosts and availability,
and see everything on a map.

LLM used: Claude (I used it to review my code and help me rewrite a few parts,
see the skill tags below).
Data from Inside Airbnb (insideairbnb.com), licensed CC BY 4.0.

Run with: streamlit run airbnb_app.py
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import pydeck as pdk

# --------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------
DATA_FILE = "data/airbnb_camb_listings.csv"
BANNER = "images/banner.png"
CAMB_LAT = 42.3736
CAMB_LON = -71.1097

#[DICT_DRIVEN] AUGMENT – one dictionary drives the room type colors, labels and descriptions
# I started with just a color dictionary for the map. Then I realized the
# label and the one-line description for each room type were sitting in
# separate if statements, so I put them all into one dict of dicts. The
# color_name is just the plain word for the map legend.
# Example: ROOM_INFO["Private Room"]["color"] gives [255, 140, 0] and
# ROOM_INFO["Private Room"]["color_name"] gives "orange".
ROOM_INFO = {
    "Entire Home/Apt": {"color": [31, 119, 180], "color_name": "blue",
                        "label": "Entire place",
                        "desc": "You get the whole apartment or house."},
    "Private Room": {"color": [255, 140, 0], "color_name": "orange",
                     "label": "Private room",
                     "desc": "Your own bedroom, shared common areas."},
    "Hotel Room": {"color": [44, 160, 44], "color_name": "green",
                   "label": "Hotel room",
                   "desc": "A room in a licensed hotel listed on Airbnb."},
    "Shared Room": {"color": [214, 39, 40], "color_name": "red",
                    "label": "Shared room",
                    "desc": "A bed in a room shared with other guests."},
}


# --------------------------------------------------------------------
# Loading and cleaning
# --------------------------------------------------------------------
def load_data():
    #[INPUT_CHECK] AUGMENT – try/except around reading the csv
    # If the file is missing (for example someone runs the app from the wrong
    # folder) pandas throws FileNotFoundError and the whole app crashes with a
    # red traceback. I catch it and return an empty frame so the app can show
    # a normal message instead.
    try:
        df = pd.read_csv(DATA_FILE)
    except FileNotFoundError:
        return pd.DataFrame()

    #[STR_CLEAN] cleaning the text columns
    # Some neighborhood and room type values could have extra spaces or odd
    # capitalization, so I strip and title() them. "entire home/apt " becomes
    # "Entire Home/Apt". That way every group-by uses the same spelling.
    df["neighbourhood"] = df["neighbourhood"].astype(str).str.strip().str.title()
    # title() turns "Area 2/MIT" into "Area 2/Mit", so I put MIT back
    df["neighbourhood"] = df["neighbourhood"].str.replace("/Mit", "/MIT")
    df["room_type"] = df["room_type"].astype(str).str.strip().str.title()
    # price is already a number in the csv, blanks come in as NaN
    df["price"] = df["price"].astype(float)
    df["minimum_nights"] = df["minimum_nights"].fillna(1).astype(int)
    return df


def priced(df):
    # for any price question I only keep rows that actually have a price
    return df.dropna(subset=["price"])


#[AI_REWRITE] REVISE / REWRITE – loop average with each step commented
#[MANUAL_CALC] – I compute the mean by hand and compare it to pandas .mean()
# My first version of this was one line (sum(prices)/len(prices)) and it
# crashed on an empty list. I asked Claude to review it and rewrote it so each
# step is its own commented line and the empty case returns 0.
# Example: [100, 200, 300] -> total 600, count 3, average 200.0
def loop_average(values):
    total = 0            # running sum of every price I have seen so far
    count = 0            # how many prices I have added
    for v in values:     # look at each price one at a time
        total = total + v
        count = count + 1
    if count == 0:       # avoid dividing by zero when nothing matched
        return 0
    return total / count


#[LOOP_VS_PANDAS] count listings per neighborhood two ways and check they match
# First I count with a plain loop and a dictionary (the way we learned in
# class), then with value_counts(). If the two don't match I print a note to
# the console so I know I did the loop wrong.
# Example: ["Agassiz", "Riverside", "Agassiz"] -> {"Agassiz": 2, "Riverside": 1}
def count_by_hood(df):
    counts = {}
    for hood in df["neighbourhood"]:
        if hood in counts:
            counts[hood] = counts[hood] + 1
        else:
            counts[hood] = 1
    pandas_counts = df["neighbourhood"].value_counts().to_dict()
    if counts != pandas_counts:
        print("loop count and pandas count do not match")
    return counts


#[LIST_COMP] IDENTIFY & EXPLAIN – dropdown labels with a listing count
# I wanted the multiselect to show "Mid-Cambridge (197)" instead of just the
# name so the user can tell which neighborhoods have a lot of options. The
# comprehension builds one string per key in the counts dict, sorted A to Z.
# Example: {"Agassiz": 83} -> ["Agassiz (83)"]
def hood_labels(counts):
    return [f"{h} ({counts[h]})" for h in sorted(counts)]


def strip_count(label):
    # "Mid-Cambridge (197)" -> "Mid-Cambridge"
    return label.split(" (")[0]


# --------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------
#[REUSE_FUNC] REVISE / REWRITE – one bar chart function with default params
# I had almost the same 10 lines of matplotlib pasted three times (Q2 price
# chart, Q3 top hosts chart, and the Home overview). I rewrote it as one
# function with defaults for color and top_n so each call is one line.
# Example: bar_chart(avg_df, "price", "Average price") draws the first 13
# rows in steelblue; bar_chart(hosts, "listings", "Top hosts", "darkorange", 10)
# draws 10 orange bars.
def bar_chart(df, col, title, color="steelblue", top_n=13, ylabel="Price per night ($)"):
    data = df.head(top_n)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(data.index.astype(str), data[col], color=color, edgecolor="black")
    ax.set_title(title, fontsize=14, weight="bold")
    ax.set_xlabel("Neighbourhood" if "price" in col else "Host")
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    return fig


def cap_price(p):
    # keep the dot size reasonable: anything under 50 counts as 50 and
    # anything over 800 counts as 800, so one $6,000 listing does not
    # cover the whole map. a missing price gets a default of 100.
    if pd.isna(p):
        return 100
    elif p < 50:
        return 50
    elif p > 800:
        return 800
    else:
        return p


def make_map(df, zoom=12):
    # pydeck map, color comes from the ROOM_INFO dictionary and radius from price
    d = df.copy()
    d["color"] = [ROOM_INFO.get(r, {"color": [120, 120, 120]})["color"] for r in d["room_type"]]
    d["radius"] = [cap_price(p) / 4 + 20 for p in d["price"]]
    d["price_txt"] = d["price"].apply(lambda p: "no price listed" if pd.isna(p) else f"${p:,.0f}")
    layer = pdk.Layer("ScatterplotLayer", data=d, get_position="[longitude, latitude]",
                      get_fill_color="color", get_radius="radius", pickable=True, opacity=0.6)
    tip = {"html": "<b>{name}</b><br>{neighbourhood}<br>{price_txt} per night<br>{room_type}",
           "style": {"backgroundColor": "#2a5d8f", "color": "white"}}
    view = pdk.ViewState(latitude=CAMB_LAT, longitude=CAMB_LON, zoom=zoom)
    return pdk.Deck(layers=[layer], initial_view_state=view, tooltip=tip,
                    map_style="light")


# --------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------
def page_home(df):
    st.header("Welcome")
    st.write("This app looks at Airbnb listings in Cambridge, MA so a visiting family or grad "
             "student can find a fairly priced short stay in a good neighborhood. Use the sidebar "
             "to pick a page.")
    st.write(f"Listings: {len(df):,}")
    st.write(f"Neighbourhoods: {df['neighbourhood'].nunique()}")
    st.write(f"Median price: ${priced(df)['price'].median():,.0f}")
    st.write("**Room types in this data:**")
    for rt in ROOM_INFO:
        n = (df["room_type"] == rt).sum()
        if n > 0:
            st.write(f"- {ROOM_INFO[rt]['label']}: {ROOM_INFO[rt]['desc']} ({n} listings)")
    counts = count_by_hood(df)
    cdf = pd.DataFrame({"listings": counts}).sort_values("listings", ascending=False)
    st.pyplot(bar_chart(cdf, "listings", "Number of listings by neighbourhood",
                        color="seagreen", ylabel="Listings"))
    st.caption("Heads up: 368 of the 1,462 listings have no price. They still show up in counts "
               "and on the map but are left out of every price calculation.")


def page_q1(df):
    st.header("Q1: Find a place")
    st.write("Which listings of a room type in the neighbourhoods you pick cost under your "
             "budget and have at least some reviews?")
    counts = count_by_hood(df)
    rooms = st.multiselect("Room type", list(ROOM_INFO.keys())[:3],
                           default=["Entire Home/Apt", "Private Room"])
    labels = hood_labels(counts)
    start = [l for l in labels if l.startswith("Mid-Cambridge") or l.startswith("Riverside")]
    picked = st.multiselect("Neighbourhood(s)", labels, default=start)
    hoods = [strip_count(p) for p in picked]

    #[INPUT_CHECK] AUGMENT – checking the budget the user types in
    # number_input already blocks letters, but a budget of 0 or something
    # below the cheapest listing ($37) would always return nothing. I check
    # the value and warn instead of silently showing an empty table.
    budget = st.number_input("Max price per night ($)", min_value=0, value=250, step=10)
    if budget < 37:
        st.warning("The cheapest listing in Cambridge is $37, so raise the budget a bit.")
    min_rev = st.slider("Minimum number of reviews", 0, 100, 5)

    if len(hoods) == 0 or len(rooms) == 0:
        st.info("Pick at least one neighbourhood and one room type to see results.")
        return
    p = priced(df)
    hits = p[(p["room_type"].isin(rooms)) & (p["neighbourhood"].isin(hoods)) &
             (p["price"] <= budget) & (p["number_of_reviews"] >= min_rev)]
    hits = hits.sort_values("price")
    if len(hits) == 0:
        st.warning("Nothing matched. Try a bigger budget, fewer reviews or another neighbourhood.")
        return
    st.success(f"{len(hits)} listings match (out of {len(p)} with a price).")
    st.write("Reviews are only a rough demand proxy; a new listing can be great and still have zero.")
    show = hits[["name", "neighbourhood", "room_type", "price", "minimum_nights",
                 "number_of_reviews", "availability_365"]]
    st.dataframe(show.reset_index(drop=True), width="stretch")
    st.pydeck_chart(make_map(hits, zoom=13))


def page_q2(df):
    st.header("Q2: Compare neighbourhoods")
    st.write("How does the price compare across neighbourhoods for one room type?")
    stat = st.radio("Statistic", ["Average", "Median"], horizontal=True)
    room = st.selectbox("Room type", ["Entire Home/Apt", "Private Room"])
    min_n = st.slider("Only show neighbourhoods with at least this many priced listings", 1, 50, 5)
    p = priced(df)
    p = p[p["room_type"] == room]
    g = p.groupby("neighbourhood")["price"]
    if stat == "Average":
        res = g.mean()
    else:
        res = g.median()
    tbl = pd.DataFrame({"price": res.round(0), "listings": g.size()})
    tbl = tbl[tbl["listings"] >= min_n].sort_values("price", ascending=False)
    if len(tbl) == 0:
        st.warning("No neighbourhood has that many listings for this room type. Lower the slider.")
        return
    st.pyplot(bar_chart(tbl, "price", f"{stat} nightly price for {ROOM_INFO[room]['label']}"))
    st.dataframe(tbl, width="stretch")

    # here is the manual average check for the cheapest shown neighbourhood
    hood = tbl.index[-1]
    vals = p[p["neighbourhood"] == hood]["price"].tolist()
    st.write(f"Check: my loop average for {hood} is ${loop_average(vals):,.2f} and pandas "
             f".mean() gives ${p[p['neighbourhood'] == hood]['price'].mean():,.2f}. Same answer.")
    st.caption("Average is pulled up by a few very expensive places (max is $6,175), so median "
               "is usually the fairer number for a visitor on a budget.")


def page_q3(df):
    st.header("Q3: Hosts and availability")
    st.write("Which hosts have the most listings, and how available are places in a "
             "neighbourhood if you only want a short minimum stay?")
    counts = count_by_hood(df)
    hood = strip_count(st.selectbox("Neighbourhood", hood_labels(counts)))
    max_nights = st.slider("Maximum minimum-nights you would accept", 1, 30, 3)
    sel = df[(df["neighbourhood"] == hood) & (df["minimum_nights"] <= max_nights)]
    st.write(f"{len(sel)} listings in {hood} with minimum nights of {max_nights} or less "
             f"(price is not needed here so all listings are included).")
    if len(sel) == 0:
        st.warning("No listings match. Raise the minimum nights slider.")
        return

    hosts = sel.groupby("host_name").size().sort_values(ascending=False)
    hosts = pd.DataFrame({"listings": hosts})
    st.pyplot(bar_chart(hosts, "listings", f"Hosts with the most listings in {hood}",
                        color="darkorange", top_n=10, ylabel="Number of listings"))
    st.dataframe(hosts.head(10), width="stretch")

    # histogram of availability
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.hist(sel["availability_365"], bins=12, color="mediumpurple", edgecolor="black")
    ax.set_title(f"Days available in the next year, {hood}", fontsize=14, weight="bold")
    ax.set_xlabel("availability_365 (days)")
    ax.set_ylabel("Number of listings")
    plt.tight_layout()
    st.pyplot(fig)
    st.write(f"Median availability in {hood}: {sel['availability_365'].median():.0f} days.")

    # pie of room type share using the dictionary colors
    share = sel["room_type"].value_counts()
    cols = [[c / 255 for c in ROOM_INFO.get(r, {"color": [120, 120, 120]})["color"]] for r in share.index]
    fig2, ax2 = plt.subplots(figsize=(5, 5))
    ax2.pie(share, labels=share.index, colors=cols, autopct="%1.0f%%", startangle=90,
            wedgeprops={"edgecolor": "white"})
    ax2.set_title(f"Room type share in {hood}", fontsize=14, weight="bold")
    st.pyplot(fig2)
    st.caption("A listing with 0 days available is probably booked solid or paused, so a low "
               "number is not always bad news for the host.")


def page_map(df):
    st.header("Map of all listings")
    st.write("Color is the room type, dot size grows with price. Hover a dot for details. "
             "Listings with no price are drawn at a default small size.")
    # legend, one line per room type that is actually in the data
    for rt in ROOM_INFO:
        if rt in df["room_type"].values:
            st.write(f"{ROOM_INFO[rt]['color_name'].title()} dots = {ROOM_INFO[rt]['label']}")
    st.pydeck_chart(make_map(df))


def page_about(df):
    st.header("About the data")
    st.write("Source: Inside Airbnb (insideairbnb.com), Cambridge MA listings, Sept 2026 "
             "snapshot. Licensed CC BY 4.0.")
    st.write(f"- {len(df):,} listings, {df['price'].isna().sum()} with no price "
             "(these are dropped only for price questions)")
    st.write("- `neighbourhood_group` is empty for every row so I ignored it.")
    st.write("- Reviews are a stand in for demand; Airbnb does not share bookings.")
    st.write("- Prices are what the host set on the snapshot day, not what you would actually pay "
             "with fees and taxes.")
    st.dataframe(df.head(20), width="stretch")


# --------------------------------------------------------------------
# Main
# --------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Cambridge Airbnb Explorer", layout="wide")
    st.image(BANNER, width="stretch")
    df = load_data()
    if len(df) == 0:
        st.error(f"Could not find {DATA_FILE}. Run the app from the app folder.")
        return
    pages = ["Home / Overview", "Q1 Find a place", "Q2 Compare neighborhoods",
             "Q3 Hosts and availability", "Map", "About the data"]
    choice = st.sidebar.radio("Go to", pages)
    st.sidebar.write("Santiago Kadadihi, CS230-7")
    if choice == pages[0]:
        page_home(df)
    elif choice == pages[1]:
        page_q1(df)
    elif choice == pages[2]:
        page_q2(df)
    elif choice == pages[3]:
        page_q3(df)
    elif choice == pages[4]:
        page_map(df)
    else:
        page_about(df)


main()
