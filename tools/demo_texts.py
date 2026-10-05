"""The made-up demo contents of the screenshot tools in English and French (German is the source).

Used by demo-screenshots-ubuntu.py and demo-examples-ubuntu.py with LINOTES_LANGUAGE=en|fr: every visible
text that is stored passes through translate(); spans (bold, highlight, note links) are moved along."""

EN = {
    # notes
    "Reisen": "Travel", "Rezepte": "Recipes", "Haushalt": "Household",
    "Radtour Kühlungsborn": "Bike tour Kühlungsborn",
    "Rund 42 km, flach und fast immer am Wasser.": "About 42 km, flat and almost always by the water.",
    "Start am Bahnhof Kühlungsborn West": "Start at Kühlungsborn West station",
    "Steilküste bis Heiligendamm": "Along the cliffs to Heiligendamm",
    "Mittag im Café am Kamp": "Lunch at Café am Kamp",
    "Zurück durch den Gespensterwald": "Back through the Ghost Forest",
    "Wochenende an der Ostsee": "Weekend on the Baltic",
    "Freitag nach der Arbeit los, Rückfahrt Sonntagabend. Zimmer mit Meerblick ist reserviert.":
        "Leave Friday after work, back Sunday evening. Room with sea view is booked.",
    "Zimmer mit Meerblick": "Room with sea view",
    "Packliste": "Packing list", "Badesachen und Handtücher": "Swimwear and towels", "Sonnencreme": "Sunscreen",
    "Fahrradschloss und Helm": "Bike lock and helmet", "Ladekabel und Powerbank": "Charger and power bank",
    "Budget": "Budget", "Posten": "Item", "Betrag": "Amount", "Wer": "Who", "Unterkunft": "Accommodation",
    "Bahn": "Train", "Essen": "Food", "beide": "both",
    "Route: Radtour Kühlungsborn": "Route: Bike tour Kühlungsborn",
    "Omas Apfelkuchen": "Grandma’s apple cake", "Zutaten": "Ingredients", "6 säuerliche Äpfel": "6 tart apples",
    "200 g Butter, 180 g Zucker": "200 g butter, 180 g sugar", "3 Eier, 300 g Mehl, 1 Päckchen Backpulver": "3 eggs, 300 g flour, 1 sachet baking powder",
    "Zubereitung": "Method", "Butter und Zucker schaumig schlagen, Eier einzeln unterrühren.": "Cream the butter and sugar, beat in the eggs one at a time.",
    "Mehl und Backpulver unterheben, Teig in die Form.": "Fold in flour and baking powder, pour the batter into the tin.",
    "Äpfel vierteln, einritzen, dicht auf den Teig setzen.": "Quarter the apples, score them, place them close together on the batter.",
    "45 Minuten bei 180 °C backen.": "Bake for 45 minutes at 180 °C.", "Mit Sahne servieren – Oma bestand darauf.": "Serve with cream – Grandma insisted.",
    "Haushaltsbuch Oktober": "Household budget October", "Fixkosten: 850 + 74 + 35 = 959": "Fixed costs: 850 + 74 + 35 = 959",
    "Lebensmittel: 412 / 2 = 206": "Groceries: 412 / 2 = 206", "Sparrate: 959 * 0,1 = 95,9": "Savings: 959 * 0,1 = 95,9",
    "Rechnen geht einfach mit = am Zeilenende": "Calculate simply with = at the end of the line",
    "Elternabend 2b": "Parents’ evening 2b", "Kurz besprochen: Lieferung kommt Dienstag, Mia übernimmt die Abholung.":
        "Quick chat: the delivery comes on Tuesday, Mia will pick it up.", "Dienstag": "Tuesday",
    "Aufnahme 2026-10-01 19-30.ogg": "Recording 2026-10-01 19-30.ogg", "Ausflug Zoo – Elternbrief.pdf": "Zoo trip – letter to parents.pdf",
    "Unterschrift bis Freitag abgeben": "Hand in signature by Friday", "10 € Busgeld mitgeben": "Give €10 for the bus",
    "Geschenkideen": "Gift ideas", "Kochkurs Thai": "Thai cooking class", "Konzertkarten": "Concert tickets",
    "Kletterhalle – Zehnerkarte": "Climbing gym – 10-visit pass", "Bluetooth-Lautsprecher": "Bluetooth speaker",
    "Zählerstände": "Meter readings", "Strom 24 518 kWh · Gas 8 214 m³ · Wasser 312 m³": "Electricity 24,518 kWh · Gas 8,214 m³ · Water 312 m³",
    # list
    "Hafermilch": "Oat milk", "Äpfel (Boskop)": "Apples (Bramley)", "Vollkornbrot": "Wholemeal bread", "Kaffeebohnen": "Coffee beans",
    "Basilikum": "Basil", "Butter": "Butter", "Spülmaschinentabs": "Dishwasher tablets",
    # board
    "Steuererklärung abgeben": "File tax return", "Belege liegen im Ordner „Haushalt“.": "Receipts are in the “Household” folder.",
    "Fahrrad zur Inspektion": "Bike in for a service", "Fenster putzen": "Clean the windows", "Gartenhaus planen": "Plan the garden shed",
    "Projektplan steht, Material bestellen.": "Project plan is ready, order materials.", "Fotobuch Sommerurlaub": "Photo book summer holiday",
    "Geburtstagsgeschenk für Mia": "Birthday present for Mia",
    # plans
    "Putzplan WG": "Flat cleaning rota", "Ben (Urlaub)": "Ben (holiday)", "Stundenplan Emma": "Emma’s timetable",
    "Deutsch": "German", "Mathe": "Maths", "Englisch": "English", "Sport": "PE", "Kunst": "Art", "Musik": "Music",
    "Sachkunde": "Science", "Religion": "RE", "Förder": "Support", "Gartenhaus bauen": "Build the garden shed",
    "Planung und Genehmigung": "Planning and permit", "Fundament gießen": "Pour the foundation", "Material liefern": "Materials delivered",
    "Aufbau Wände und Dach": "Walls and roof", "Streichen": "Painting", "Einweihung": "Housewarming",
    "Dienstplan Station 3": "Duty rota Ward 3", "Früh": "Early", "Spät": "Late", "Nacht": "Night", "Frei": "Off",
    # development project
    "Spurhalteassistent LKA – Steuergerät": "Lane keeping assist LKA – control unit",
    "Analyse": "Analysis", "Umsetzung": "Implementation", "Verifikation": "Verification", "Freigegeben": "Released",
    "Warnschwelle bei Nässe anpassen": "Adjust warning threshold in the wet", "Diagnose-Trouble-Code für Kamerablindheit": "Diagnostic trouble code for camera blindness",
    "Lenkmoment-Eingriff auf 3 Nm begrenzen": "Limit steering torque intervention to 3 Nm",
    "ASIL B betroffen (Sicherheitsziel SG-02: kein ungewollter Lenkeingriff > 3 Nm). Änderung an SW-Komponente LKA_Ctrl, Schnittstelle zum EPS unverändert. Regressionsumfang: HIL-Szenarien 12–18. Kein Einfluss auf ESC/ABS.":
        "ASIL B affected (safety goal SG-02: no unintended steering intervention > 3 Nm). Change to SW component LKA_Ctrl, interface to the EPS unchanged. Regression scope: HIL scenarios 12–18. No effect on ESC/ABS.",
    "Spurerkennung bei Baustellenmarkierung (gelb)": "Lane detection with roadworks markings (yellow)",
    "QM, kein Sicherheitsziel betroffen. Kalibrierdaten der Kamera, neue Parameter-Tabelle. Bestehende Freigabe-Tests ausreichend.":
        "QM, no safety goal affected. Camera calibration data, new parameter table. Existing release tests sufficient.",
    "Abschaltung unter 60 km/h": "Deactivation below 60 km/h",
    "ASIL A. Funktionsgrenze in Zustandsautomat LKA_Mode. Wirkt nur auf Aktivierung.": "ASIL A. Function limit in state machine LKA_Mode. Affects activation only.",
    "SIL-Test TC-LKA-031..036 bestanden, HIL-Lauf 2026-09-30 i. O., Fahrversuch ausstehend.": "SIL test TC-LKA-031..036 passed, HIL run 2026-09-30 OK, road test pending.",
    "Hands-off-Erkennung 15 s": "Hands-off detection 15 s",
    "ASIL B (SG-04). Erkennung über Lenkmomentsensor, Warnkaskade optisch → akustisch → Abschaltung.": "ASIL B (SG-04). Detection via steering torque sensor, warning cascade visual → acoustic → deactivation.",
    "Fahrversuch 2 × 500 km i. O., HIL 100 % bestanden, Review RV-118 abgeschlossen.": "Road test 2 × 500 km OK, HIL 100 % passed, review RV-118 completed.",
    "LKA: gelbe Fahrbahnmarkierung bevorzugen (Baustellenmodus)": "LKA: prefer yellow lane markings (roadworks mode)",
    "LKA: Aktivierungsschwelle 60 km/h, Hysterese 5 km/h": "LKA: activation threshold 60 km/h, hysteresis 5 km/h",
    "Tests: SIL-Szenarien Abschaltgrenze": "Tests: SIL scenarios deactivation limit", "LKA: Hands-off-Warnkaskade": "LKA: hands-off warning cascade",
    "SIL-Testlauf LKA – Abschaltgrenze": "SIL test run LKA – deactivation limit", "bestanden": "passed",
    "HIL-Protokoll 2026-09-30.pdf": "HIL report 2026-09-30.pdf", "SIL-Ergebnis TC-LKA-031–036.png": "SIL result TC-LKA-031–036.png",
}

FR = {
    "Reisen": "Voyages", "Rezepte": "Recettes", "Haushalt": "Maison",
    "Radtour Kühlungsborn": "Balade à vélo Kühlungsborn",
    "Rund 42 km, flach und fast immer am Wasser.": "Environ 42 km, plat et presque toujours au bord de l’eau.",
    "Start am Bahnhof Kühlungsborn West": "Départ à la gare de Kühlungsborn West",
    "Steilküste bis Heiligendamm": "Les falaises jusqu’à Heiligendamm",
    "Mittag im Café am Kamp": "Déjeuner au Café am Kamp",
    "Zurück durch den Gespensterwald": "Retour par la forêt des fantômes",
    "Wochenende an der Ostsee": "Week-end sur la Baltique",
    "Freitag nach der Arbeit los, Rückfahrt Sonntagabend. Zimmer mit Meerblick ist reserviert.":
        "Départ vendredi après le travail, retour dimanche soir. La chambre avec vue sur la mer est réservée.",
    "Zimmer mit Meerblick": "chambre avec vue sur la mer",
    "Packliste": "Liste de bagages", "Badesachen und Handtücher": "Maillots et serviettes", "Sonnencreme": "Crème solaire",
    "Fahrradschloss und Helm": "Antivol et casque", "Ladekabel und Powerbank": "Chargeur et batterie externe",
    "Budget": "Budget", "Posten": "Poste", "Betrag": "Montant", "Wer": "Qui", "Unterkunft": "Hébergement",
    "Bahn": "Train", "Essen": "Repas", "beide": "les deux",
    "Route: Radtour Kühlungsborn": "Itinéraire : Balade à vélo Kühlungsborn",
    "Omas Apfelkuchen": "Gâteau aux pommes de mamie", "Zutaten": "Ingrédients", "6 säuerliche Äpfel": "6 pommes acidulées",
    "200 g Butter, 180 g Zucker": "200 g de beurre, 180 g de sucre", "3 Eier, 300 g Mehl, 1 Päckchen Backpulver": "3 œufs, 300 g de farine, 1 sachet de levure",
    "Zubereitung": "Préparation", "Butter und Zucker schaumig schlagen, Eier einzeln unterrühren.": "Battre le beurre et le sucre, incorporer les œufs un à un.",
    "Mehl und Backpulver unterheben, Teig in die Form.": "Ajouter farine et levure, verser la pâte dans le moule.",
    "Äpfel vierteln, einritzen, dicht auf den Teig setzen.": "Couper les pommes en quartiers, les inciser, les serrer sur la pâte.",
    "45 Minuten bei 180 °C backen.": "Cuire 45 minutes à 180 °C.", "Mit Sahne servieren – Oma bestand darauf.": "Servir avec de la crème – mamie y tenait.",
    "Haushaltsbuch Oktober": "Budget du ménage octobre", "Fixkosten: 850 + 74 + 35 = 959": "Charges fixes : 850 + 74 + 35 = 959",
    "Lebensmittel: 412 / 2 = 206": "Courses : 412 / 2 = 206", "Sparrate: 959 * 0,1 = 95,9": "Épargne : 959 * 0,1 = 95,9",
    "Rechnen geht einfach mit = am Zeilenende": "Calculer, c’est simple avec = en fin de ligne",
    "Elternabend 2b": "Réunion parents CE1", "Kurz besprochen: Lieferung kommt Dienstag, Mia übernimmt die Abholung.":
        "Vu rapidement : la livraison arrive mardi, Mia s’occupe du retrait.", "Dienstag": "mardi",
    "Aufnahme 2026-10-01 19-30.ogg": "Enregistrement 2026-10-01 19-30.ogg", "Ausflug Zoo – Elternbrief.pdf": "Sortie au zoo – courrier aux parents.pdf",
    "Unterschrift bis Freitag abgeben": "Rendre la signature avant vendredi", "10 € Busgeld mitgeben": "Donner 10 € pour le bus",
    "Geschenkideen": "Idées cadeaux", "Kochkurs Thai": "Cours de cuisine thaï", "Konzertkarten": "Places de concert",
    "Kletterhalle – Zehnerkarte": "Salle d’escalade – carte 10 entrées", "Bluetooth-Lautsprecher": "Enceinte Bluetooth",
    "Zählerstände": "Relevés de compteurs", "Strom 24 518 kWh · Gas 8 214 m³ · Wasser 312 m³": "Électricité 24 518 kWh · Gaz 8 214 m³ · Eau 312 m³",
    "Hafermilch": "Lait d’avoine", "Äpfel (Boskop)": "Pommes (reinettes)", "Vollkornbrot": "Pain complet", "Kaffeebohnen": "Café en grains",
    "Basilikum": "Basilic", "Butter": "Beurre", "Spülmaschinentabs": "Tablettes lave-vaisselle",
    "Steuererklärung abgeben": "Déclaration d’impôts", "Belege liegen im Ordner „Haushalt“.": "Les justificatifs sont dans le dossier « Maison ».",
    "Fahrrad zur Inspektion": "Révision du vélo", "Fenster putzen": "Laver les vitres", "Gartenhaus planen": "Prévoir l’abri de jardin",
    "Projektplan steht, Material bestellen.": "Le plan est prêt, commander le matériel.", "Fotobuch Sommerurlaub": "Livre photo vacances d’été",
    "Geburtstagsgeschenk für Mia": "Cadeau d’anniversaire pour Mia",
    "Putzplan WG": "Planning de ménage colocation", "Ben (Urlaub)": "Ben (congés)", "Stundenplan Emma": "Emploi du temps d’Emma",
    "Deutsch": "Français", "Mathe": "Maths", "Englisch": "Anglais", "Sport": "Sport", "Kunst": "Arts", "Musik": "Musique",
    "Sachkunde": "Sciences", "Religion": "Éthique", "Förder": "Soutien", "Gartenhaus bauen": "Construire l’abri de jardin",
    "Planung und Genehmigung": "Plans et permis", "Fundament gießen": "Couler la dalle", "Material liefern": "Livraison du matériel",
    "Aufbau Wände und Dach": "Murs et toit", "Streichen": "Peinture", "Einweihung": "Inauguration",
    "Dienstplan Station 3": "Planning service 3", "Früh": "Matin", "Spät": "Soir", "Nacht": "Nuit", "Frei": "Repos",
    "Spurhalteassistent LKA – Steuergerät": "Aide au maintien de voie LKA – calculateur",
    "Analyse": "Analyse", "Umsetzung": "Réalisation", "Verifikation": "Vérification", "Freigegeben": "Libéré",
    "Warnschwelle bei Nässe anpassen": "Adapter le seuil d’alerte sur chaussée mouillée", "Diagnose-Trouble-Code für Kamerablindheit": "Code défaut de diagnostic pour caméra aveuglée",
    "Lenkmoment-Eingriff auf 3 Nm begrenzen": "Limiter l’intervention du couple de braquage à 3 Nm",
    "ASIL B betroffen (Sicherheitsziel SG-02: kein ungewollter Lenkeingriff > 3 Nm). Änderung an SW-Komponente LKA_Ctrl, Schnittstelle zum EPS unverändert. Regressionsumfang: HIL-Szenarien 12–18. Kein Einfluss auf ESC/ABS.":
        "ASIL B concerné (objectif de sécurité SG-02 : pas d’intervention de braquage involontaire > 3 Nm). Modification du composant logiciel LKA_Ctrl, interface avec l’EPS inchangée. Étendue de régression : scénarios HIL 12–18. Aucun effet sur ESC/ABS.",
    "Spurerkennung bei Baustellenmarkierung (gelb)": "Détection de voie avec marquage de chantier (jaune)",
    "QM, kein Sicherheitsziel betroffen. Kalibrierdaten der Kamera, neue Parameter-Tabelle. Bestehende Freigabe-Tests ausreichend.":
        "QM, aucun objectif de sécurité concerné. Données d’étalonnage de la caméra, nouvelle table de paramètres. Tests de libération existants suffisants.",
    "Abschaltung unter 60 km/h": "Désactivation sous 60 km/h",
    "ASIL A. Funktionsgrenze in Zustandsautomat LKA_Mode. Wirkt nur auf Aktivierung.": "ASIL A. Limite de fonction dans l’automate LKA_Mode. N’agit que sur l’activation.",
    "SIL-Test TC-LKA-031..036 bestanden, HIL-Lauf 2026-09-30 i. O., Fahrversuch ausstehend.": "Test SIL TC-LKA-031..036 réussi, essai HIL 2026-09-30 OK, essai routier en attente.",
    "Hands-off-Erkennung 15 s": "Détection mains libres 15 s",
    "ASIL B (SG-04). Erkennung über Lenkmomentsensor, Warnkaskade optisch → akustisch → Abschaltung.": "ASIL B (SG-04). Détection par capteur de couple, cascade d’alertes visuelle → sonore → désactivation.",
    "Fahrversuch 2 × 500 km i. O., HIL 100 % bestanden, Review RV-118 abgeschlossen.": "Essai routier 2 × 500 km OK, HIL réussi à 100 %, revue RV-118 terminée.",
    "LKA: gelbe Fahrbahnmarkierung bevorzugen (Baustellenmodus)": "LKA : privilégier le marquage jaune (mode chantier)",
    "LKA: Aktivierungsschwelle 60 km/h, Hysterese 5 km/h": "LKA : seuil d’activation 60 km/h, hystérésis 5 km/h",
    "Tests: SIL-Szenarien Abschaltgrenze": "Tests : scénarios SIL limite de désactivation", "LKA: Hands-off-Warnkaskade": "LKA : cascade d’alertes mains libres",
    "SIL-Testlauf LKA – Abschaltgrenze": "Essai SIL LKA – limite de désactivation", "bestanden": "réussi",
    "HIL-Protokoll 2026-09-30.pdf": "Rapport HIL 2026-09-30.pdf", "SIL-Ergebnis TC-LKA-031–036.png": "Résultat SIL TC-LKA-031–036.png",
}

TABLES = {"en": EN, "fr": FR}
TEXT_KEYS = ("x", "name", "title", "notes", "impact", "verification", "text", "n", "s")


def translator(lang):
    table = TABLES.get(lang, {})

    def text(value):
        return table.get(value, value) if isinstance(value, str) else value

    def block(b):
        b = dict(b)
        if b.get("t") == "table" and isinstance(b.get("r"), list):
            b["r"] = [[text(cell) for cell in row] for row in b["r"]]
            b["x"] = "\n".join(" | ".join(row) for row in b["r"])
            return b
        old = b.get("x")
        if isinstance(old, str):
            new = text(old)
            if new != old and isinstance(b.get("s"), list):
                spans = []
                for start, end, name in b["s"]:
                    part = text(old[start:end])
                    at = new.find(part)
                    if at < 0:  # the part's translation must appear in the line's translation
                        raise ValueError(f"Markierung „{part}“ fehlt in „{new}“")
                    spans.append([at, at + len(part), name])
                b["s"] = spans
            b["x"] = new
        if isinstance(b.get("n"), str):
            b["n"] = text(b["n"])
        return b

    def data(value, key=None):
        if not table:
            return value
        if key == "body" and isinstance(value, list):
            return [block(b) if isinstance(b, dict) else b for b in value]
        if isinstance(value, dict):
            return {k: data(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [data(v, key) for v in value]
        if isinstance(value, str) and key in TEXT_KEYS + ("rows", "labels"):
            return text(value)
        return value
    return text, data
