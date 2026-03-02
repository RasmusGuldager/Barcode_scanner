import sqlite3
import os

# Stien til databasen (peger ned i din data-mappe)
db_path = os.path.join('data', 'database.db')

def main():
    # Tjek om filen overhovedet findes endnu
    if not os.path.exists(db_path):
        print(f"Fejl: Kunne ikke finde databasen på '{db_path}'.")
        print("Sørg for at køre dette script fra hovedmappen, og at Flask har oprettet databasen.")
        return

    # Åbn en direkte forbindelse til filen
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("="*40)
    print(" 📦 VAP-LAB INVENTORY MANAGER")
    print("="*40)
    print("Tip: Skriv 'exit' for at afslutte programmet.\n")

    while True:
        # 1. Spørg efter stregkoden
        barcode = input("Scan eller indtast stregkode: ").strip()
        if barcode.lower() == 'exit':
            break
        if not barcode:
            continue
            
        # 2. Spørg efter navnet
        name = input(f"Hvad hedder udstyret ({barcode})?: ").strip()
        if name.lower() == 'exit':
            break

        # 3. Prøv at gemme det i databasen
        try:
            # is_rented sættes til 0 (som betyder False / "In Storage")
            cursor.execute('''
                INSERT INTO item (barcode, name, is_rented) 
                VALUES (?, ?, 0)
            ''', (barcode, name))
            
            conn.commit() # Gem ændringen fysisk i filen
            print(f"✅ Succes! '{name}' er nu tilføjet til lageret.\n")
            
        except sqlite3.IntegrityError:
            # SQLAlchemy har sat 'unique=True' på stregkoden. 
            # SQLite kaster derfor denne fejl, hvis du scanner det samme to gange!
            print(f"❌ Fejl: Stregkoden '{barcode}' findes allerede i systemet!\n")
            
        except Exception as e:
            print(f"❌ Der skete en uventet fejl: {e}\n")

    conn.close()
    print("Lukker programmet. Hav en god dag!")

if __name__ == '__main__':
    main()