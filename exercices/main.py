from exercice_1 import analyser_code, calculer_cout

def main():
    code_source = """
def get_user(id):
    import sqlite3
    conn = sqlite3.connect('db.sqlite')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = " + str(id))
    return cursor.fetchone()
"""

    # Exercice 1 : Analyse de code
    resultat = analyser_code(code_source)
    print(resultat.content)

    # Affichage des coûts
    cout = calculer_cout(
        resultat.prompt_tokens,
        resultat.completion_tokens
    )

    print(f"\n\n**Coût théorique** : {cout:.8f} $")

if __name__ == "__main__":
    main()
