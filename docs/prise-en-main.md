# Prise en main — MCP Salesforce (client credentials)

## ⚠️ Le point qui fait échouer 9 installations sur 10 : le domaine

`SALESFORCE_INSTANCE_URL` doit contenir **l'URL personnalisée de votre org (My Domain)**.

**Pas** `login.salesforce.com`, **pas** `test.salesforce.com`. Ces deux endpoints
génériques ne servent pas le grant `client_credentials` : ils ne connaissent pas votre
connected app. C'est une contrainte de Salesforce, pas une limitation du serveur MCP.

### Où trouver cette URL

Setup → *Company Settings* → **My Domain** → champ **Current My Domain URL**.

Plus rapide : connectez-vous à l'org et lisez la barre d'adresse, c'est la partie avant
le premier `/`.

| Type d'org | Forme de l'URL |
| --- | --- |
| Production | `https://acme.my.salesforce.com` |
| Sandbox | `https://acme--uat.sandbox.my.salesforce.com` |
| Scratch / dev | `https://acme-dev-ed.develop.my.salesforce.com` |

Le nom de la sandbox fait partie du domaine (`--uat`) : une sandbox a une URL différente
de la production, ce n'est pas la même valeur avec un drapeau en plus.

### Ce que la variable accepte

Les quatre écritures suivantes donnent le même résultat :

```
SALESFORCE_INSTANCE_URL=acme
SALESFORCE_INSTANCE_URL=acme.my.salesforce.com
SALESFORCE_INSTANCE_URL=https://acme.my.salesforce.com
SALESFORCE_INSTANCE_URL=acme--uat.sandbox.my        # sandbox, forme courte
```

En cas de doute, **collez l'URL complète copiée depuis le navigateur** : c'est la forme
qui ne se discute pas.

### Symptômes d'un domaine erroné

| Message renvoyé | Cause probable |
| --- | --- |
| `invalid_client_id: client identifier invalid` | vous visez `login`/`test.salesforce.com`, ou la mauvaise org |
| `unsupported_grant_type` | « Enable Client Credentials Flow » n'est pas coché sur la connected app |
| `invalid_grant: no client credentials user enabled` | l'utilisateur *Run As* n'est pas défini |
| erreur DNS `Failed to resolve …` | faute de frappe dans le nom de domaine |

---

## Les trois étapes

### 1. Côté Salesforce

Setup → *App Manager* → votre connected app → *Edit* :

- **Enable OAuth Settings** coché
- scope `Manage user data via APIs (api)`
- **Enable Client Credentials Flow** coché
- puis *Manage* → *Edit Policies* → **Run As** : choisir l'utilisateur d'exécution

⚠️ Tous les appels du MCP s'exécutent avec les droits de cet utilisateur *Run As*.
Un compte dédié, au profil restreint, vaut mieux qu'un administrateur système.

Récupérez enfin la **Consumer Key** et le **Consumer Secret** (*Manage Consumer Details*).

### 2. Enregistrer les identifiants

```
./scripts/set-credentials.sh
```

Le script demande le domaine, la clé et le secret. Les deux secrets sont saisis en
aveugle : rien ne s'affiche, rien ne part dans l'historique du shell. Il écrit un
fichier `.env` lisible par vous seul (mode `600`).

### 3. Vérifier

```
python scripts/check_auth.py
```

Sortie attendue — les valeurs sensibles restent masquées :

```
Instance URL   : https://acme.my.salesforce.com
Client id      : 3MVG9R...TOEq (85 chars)
Auth flow      : client_credentials
Run-as user    : integration.mcp@acme.com
Test query     : ok (1 row)

OK
```

Si cette commande affiche `OK`, le serveur MCP fonctionnera.

---

## Déclaration dans le client MCP

```json
{
  "mcpServers": {
    "salesforce": {
      "command": "uvx",
      "args": ["mcp-salesforce"],
      "env": {
        "MCP_SALESFORCE_ENV_FILE": "/chemin/vers/mcp-salesforce/.env"
      }
    }
  }
}
```

Passer par `MCP_SALESFORCE_ENV_FILE` évite d'écrire le secret en clair dans un fichier de
configuration souvent synchronisé ou partagé. Les variables d'environnement définies
directement dans le bloc `env` restent prioritaires sur le fichier.
