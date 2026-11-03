import sqlite3
import json

DB_FILE = "cleancity.db"
JSON_FILE = "data.json"

def create_tables(cursor):
    cursor.execute("DROP TABLE IF EXISTS faq")
    cursor.execute("DROP TABLE IF EXISTS schedule")
    cursor.execute("DROP TABLE IF EXISTS request")

    cursor.execute("""
    CREATE TABLE faq (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        category TEXT NOT NULL,
        source_url TEXT NOT NULL
    )""")

    cursor.execute("""
    CREATE TABLE schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zone TEXT NOT NULL,
        waste_type TEXT NOT NULL,
        collection_day TEXT NOT NULL,
        frequency TEXT NOT NULL,
        notes TEXT
    )""")

    cursor.execute("""
    CREATE TABLE request (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_type TEXT NOT NULL,
        description TEXT NOT NULL,
        required_info TEXT NOT NULL,
        processing_days INTEGER NOT NULL,
        fee TEXT NOT NULL
    )""")

def seed_data(cursor):
    faqs = [
        ("What items are accepted in the residential blue recycling bin?", "Clean paper, cardboard, rigid plastic bottles (#1 and #2), glass jars, and clean aluminum or tin cans are accepted. Rinse empty.", "Recycling Guidelines", "https://www.cleancityservices.gov/recycling-faq"),
        ("Can greasy pizza boxes be placed in recycling?", "No. Food-contaminated cardboard cannot be recycled. Place soiled cardboard into the organic compost bin or general trash.", "Recycling Guidelines", "https://www.cleancityservices.gov/recycling-faq"),
        ("How do I safely dispose of household hazardous waste like paint or batteries?", "Lithium batteries, paints, solvents, and pesticides must not go in curb bins. Submit a Hazardous Pickup Request or visit the Central Depot.", "Hazardous Waste", "https://www.cleancityservices.gov/hazardous-disposal"),
        ("What time should waste bins be set out on collection day?", "Bins must be placed at the curb by 7:00 AM on scheduled collection day or after 7:00 PM the evening prior.", "Collection Rules", "https://www.cleancityservices.gov/collection-schedules"),
        ("What should I do if my waste collection was missed?", "Ensure bins were set out on time. If missed by the crew, submit a Missed Pickup Request online within 24 hours.", "Customer Support", "https://www.cleancityservices.gov/special-requests"),
        ("Are plastic grocery bags accepted in curbside recycling?", "No. Plastic bags wrap around sorting equipment. Return plastic bags to participating grocery store drop-off bins.", "Recycling Guidelines", "https://www.cleancityservices.gov/recycling-faq"),
        ("How can I replace a damaged or stolen waste bin?", "Submit a Bin Replacement Request online. Replacement carts are delivered within 3 business days.", "Bin Management", "https://www.cleancityservices.gov/special-requests"),
        ("What are the guidelines for yard waste and garden trimmings?", "Place in brown paper yard bags or green organic bins. Branches must be bundled under 4 feet in length and 2 inches in diameter.", "Yard & Organics", "https://www.cleancityservices.gov/collection-schedules"),
        ("Can styrofoam or expanded polystyrene be recycled curbside?", "No. Foam containers are not recyclable curbside. Place in general waste or drop off at designated municipal depots.", "Recycling Guidelines", "https://www.cleancityservices.gov/recycling-faq"),
        ("How do I dispose of old electronics and appliances (E-waste)?", "E-waste contains heavy metals and cannot go in general trash. Schedule a Special E-Waste Pickup or visit the municipal depot.", "E-Waste", "https://www.cleancityservices.gov/hazardous-disposal"),
        ("What materials belong in the green organic compost bin?", "Food scraps, vegetable peels, coffee grounds, paper towels, yard waste, and certified compostable packaging belong in green bins.", "Yard & Organics", "https://www.cleancityservices.gov/recycling-faq"),
        ("How does holiday waste collection work during statutory holidays?", "Collection schedules shift forward by one day following official holidays (e.g., Monday holiday shifts Monday pickup to Tuesday).", "Collection Rules", "https://www.cleancityservices.gov/collection-schedules"),
        ("Is medical waste or household sharps allowed in residential trash?", "Sharps must never be placed in general trash. Place in FDA-approved sharps containers and return to pharmacy drop-off sites.", "Hazardous Waste", "https://www.cleancityservices.gov/hazardous-disposal"),
        ("How heavy can residential waste and recycling bins be?", "Standard rolling carts have a maximum weight limit of 200 lbs. Overfilled carts will not be serviced by automated arms.", "Collection Rules", "https://www.cleancityservices.gov/collection-schedules"),
        ("Where can I drop off extra waste that exceeds regular bin capacity?", "Purchase extra waste tags at municipal centers or drop excess solid waste directly at the City Transfer Station.", "Customer Support", "https://www.cleancityservices.gov/collection-schedules")
    ]
    cursor.executemany("INSERT INTO faq (question, answer, category, source_url) VALUES (?, ?, ?, ?)", faqs)

    schedules = [
        ("Zone A - Downtown North", "General Waste", "Monday", "Weekly", "Place cart at curb before 7:00 AM."),
        ("Zone A - Downtown North", "Recycling (Blue Bin)", "Tuesday", "Bi-weekly", "Odd calendar weeks only."),
        ("Zone B - East Residential", "General Waste", "Tuesday", "Weekly", "Place cart at curb before 7:00 AM."),
        ("Zone B - East Residential", "Recycling (Blue Bin)", "Wednesday", "Bi-weekly", "Even calendar weeks only."),
        ("Zone C - West Suburbs", "General Waste", "Wednesday", "Weekly", "Place cart at curb before 7:00 AM."),
        ("Zone C - West Suburbs", "Organic Waste (Green Bin)", "Thursday", "Weekly", "Accepts food scraps and yard trimmings."),
        ("Zone D - South Industrial", "General Waste", "Thursday", "Weekly", "Heavy commercial vehicles operate early morning."),
        ("Zone D - South Industrial", "Recycling (Blue Bin)", "Friday", "Bi-weekly", "Odd calendar weeks only."),
        ("Zone E - North Heights", "Organic Waste (Green Bin)", "Friday", "Weekly", "Bundled branches under 4 feet accepted."),
        ("All City Zones", "Hazardous & E-Waste Drop-off", "Saturday", "Monthly (1st Sat)", "Central Depot open 8:00 AM - 2:00 PM.")
    ]
    cursor.executemany("INSERT INTO schedule (zone, waste_type, collection_day, frequency, notes) VALUES (?, ?, ?, ?, ?)", schedules)

    requests = [
        ("Bulk Item Pickup Request", "Schedule removal of oversized items including furniture and non-freon appliances.", "Item list, dimensions, preferred pickup date, address", 3, "Free (2 pickups/year, $25 extra)"),
        ("Bin Replacement or Repair Request", "Request repair or replacement for damaged or stolen wheelie carts.", "Bin serial number, bin size, issue description, address", 2, "Free for normal wear or stolen cart"),
        ("Household Hazardous Waste Pickup", "Doorstep pickup for motor oil, batteries, liquid paints, and chemicals.", "Chemical types, approximate volume, secure location", 5, "Free residential service"),
        ("Event & Extra Bin Temporary Rental", "Short-term rental of additional waste and recycling carts for events.", "Event date, number of carts needed, delivery address", 4, "$15 per cart/day"),
        ("Missed Collection Escalation Form", "Report missed scheduled trash, recycling, or compost pickup.", "Collection date, waste type missed, placement timestamp", 1, "Free service")
    ]
    cursor.executemany("INSERT INTO request (request_type, description, required_info, processing_days, fee) VALUES (?, ?, ?, ?, ?)", requests)

def export_json(cursor):
    cursor.execute("SELECT id, question, answer, category, source_url FROM faq")
    faqs = [{"id": r[0], "question": r[1], "answer": r[2], "category": r[3], "source_url": r[4]} for r in cursor.fetchall()]

    cursor.execute("SELECT id, zone, waste_type, collection_day, frequency, notes FROM schedule")
    schedules = [{"id": r[0], "zone": r[1], "waste_type": r[2], "collection_day": r[3], "frequency": r[4], "notes": r[5]} for r in cursor.fetchall()]

    cursor.execute("SELECT id, request_type, description, required_info, processing_days, fee FROM request")
    requests = [{"id": r[0], "request_type": r[1], "description": r[2], "required_info": r[3], "processing_days": r[4], "fee": r[5]} for r in cursor.fetchall()]

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump({"faqs": faqs, "schedules": schedules, "requests": requests}, f, indent=2)

def main():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    create_tables(cursor)
    seed_data(cursor)
    conn.commit()
    export_json(cursor)
    conn.close()
    print("Database cleancity.db created and exported to data.json successfully!")

if __name__ == "__main__":
    main()