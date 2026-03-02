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

        category = input(f"Hvilken kategori passer bedst til '{name}'?").strip()
        if category.lower() == 'exit':
            break
            
        # 3. Spørg efter ekstra info (Multiline)
        print("Ekstra info (Skriv alt hvad du vil. Tryk ENTER to gange i træk for at afslutte):")
        info_lines = []
        while True:
            line = input()
            # Hvis brugeren trykker Enter uden at skrive noget, stopper vi
            if line == "": 
                break
            info_lines.append(line)
            
        # Saml alle linjerne til én lang tekst med rigtige linjeskift (\n)
        extra_info = "\n".join(info_lines)
        
        # Hvis de bare trykkede enter med det samme, sætter vi den til None
        if not extra_info.strip():
            extra_info = None

        # 4. Prøv at gemme det i databasen (Husk at opdatere SQL-strengen)
        try:
            cursor.execute('''
                INSERT INTO item (barcode, name, category, extra_info, is_rented) 
                VALUES (?, ?, ?, ?, 0)
            ''', (barcode, name, category, extra_info))
            
            conn.commit()
            print(f"✅ Succes! '{name}' er nu tilføjet.\n")
            
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