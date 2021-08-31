import logging
from datetime import datetime, date,timezone
from telegram import ReplyKeyboardRemove, Update,InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackContext,
    CallbackQueryHandler,
    Filters,
)
import pandas as pd
from send_message import telegram_bot_sendtext
import os
PORT = int(os.environ.get('PORT', 5000))



#### Connexion avec BDD (fichiers csv pour l'instant) ###

USERS = pd.read_csv('Users.csv')
REMONTEES = pd.read_csv('remontees.csv').set_index('id')
REMONTEES_REPONSES = pd.read_csv('remontee_reponses.csv').set_index('id')
ZONES_TERRITORIALES = pd.read_csv('zones_territoriales.csv').set_index('code')

#### FONCTIONS D'AIDE ####

def verification_admin(tel_id):
# sert a determiner si un utiisateur est admin ou non, en chechant son telegram_id dans le csv
    try:
        return bool(USERS[USERS.telegram_id == tel_id]['admin'].values[0])
    except:
        False  #si l'utilisateur n'est pas trouvé cela renvoie False

def verification_user(tel_id):
# sert a determiner si un utiisateur est présent dans la bdd ou non
    return not USERS[USERS.telegram_id == tel_id].empty

def remontee_en_cours_bool(table_remontees):
#cette fonction verifie si il y a une remontee ouverte dans la bdd
    global REMONTEES  #on doit declarer la variable globale, en effet if faut etre sur de re-ouvrir le fichier a chaque fois qu'on le modifie
    REMONTEES = pd.read_csv('remontees.csv').set_index('id') #on lit le fichier
    bool = False #on initialise la reponse a Faux
    date_fin = 0
    for i in table_remontees.index: #on fait uen boucle sur toutes les remontees de la table
        date_fin = table_remontees['date_fin'][i]
        if datetime.strptime(date_fin, '%d/%m/%Y') > datetime.now(): #si on voit qu'une date est dans le futur, on stoppe la boucle et on envoie la reponse
            bool = True #la reponse devient TRUE vu qu'on a trouvé une date dans le futur
            break
    return (bool,date_fin)

def sauvegarde_remontee(table_remontees, date_limite, nom_remontee, id_user):
# cette fonction sert a sauvegarder de nouvelles remonteées proprement
    global REMONTEES
    REMONTEES = pd.read_csv('remontees.csv').set_index('id')
    new_id = max(table_remontees.index) + 1
    current_date = datetime.now().strftime("%d/%m/%Y") #toujours un probleme de timezone a regler
    table_remontees.loc[new_id] = [nom_remontee, current_date, date_limite, current_date, id_user]
    try:  #on essaie de sauvergarder, si il y a soucis on ferme
        table_remontees.to_csv('remontees.csv')
        REMONTEES = pd.read_csv('remontees.csv').set_index('id') #on reouvre pour etre sur que le bot utilise la bonne version du csv dans le futur
        return True
    except:
        return False

def sauvegarde_utilisateur(id, first_name, last_name, at_telegram):
# cette fonction sert a sauvegarder de nouveaux utilisateurs
    global USERS
    USERS = pd.read_csv('users.csv')
    try:  #on essaie de sauvergarder, si il y a soucis on ferme
        USERS.loc[len(USERS.index)] = [len(USERS.index), id, first_name, last_name, at_telegram, 0]
        USERS.to_csv('Users.csv')
        USERS = pd.read_csv('Users.csv')
        return True
    except:
        return False

def maj_remontee(nouvelle_date):
    global REMONTEES
    REMONTEES = pd.read_csv('remontees.csv').set_index('id')
    try:
        remontee_ouverte, date_limite = remontee_en_cours_bool(REMONTEES) # on recupere la date limite actuelle
        if remontee_ouverte :
            index = REMONTEES[REMONTEES.date_fin == date_limite].index # a quelle ligne cette date limite correspond t elle ?
            REMONTEES.loc[index, 'date_fin'] = nouvelle_date  #on change pour la nouvelle date
            REMONTEES.to_csv('remontees.csv')
            REMONTEES = pd.read_csv('remontees.csv').set_index('id')
            return True
        else:
            return False
    except:
        return False

#### BOT ####

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

# Numerotation des etapes possibles
ACTION_REMONTEE, DEMANDER_REMONTEE, VALIDATION_DEMANDE_REMONTEE, CONFIRMATION_CLOTURE, VALIDATION_CHANGEMENT_DATE_REMONTEE = range(5)
# numerotation des reponses possibles
ZERO, ONE, TWO, THREE, FOUR = range(5)

def start(update: Update, _: CallbackContext) -> int:
    user = update.message.from_user
    id, username = user.id, user.username
    if verification_user(id): #verifie si l'utilisateur existe dans la bdd
        if verification_admin(id):
            text = 'Bonjour ' + user.first_name + ', tu es Administrateur.'
            update.message.reply_text(text)
        else:
            try:
                zone = ZONES_TERRITORIALES[ZONES_TERRITORIALES['manager'] == username]['nom'].values[0]
                text = 'Bonjour ' + user.first_name + ', tu es référent sur la zone ' + zone + '.'
                update.message.reply_text(text)
            except:
                text = "Bonjour "+user.first_name+", il te faut un accès pour m'utiliser."
                update.message.reply_text(text)
    else:
        text = "Si tu es adhérent, connecte toi à ton compte JAM."
        update.message.reply_text(text)
        sauvegarde_utilisateur(user.id, user.first_name, user.last_name, user.username)
    return ConversationHandler.END

def remontee(update: Update, _: CallbackContext) -> int:
    try:
        user = update.message.from_user
        first_name = user.first_name
    except:
        query = update.callback_query
        query.answer()
        user = query.from_user
        first_name = user.first_name
    global REMONTEES
    REMONTEES = pd.read_csv('remontees.csv').set_index('id')
    if verification_admin(user.id):
        if remontee_en_cours_bool(REMONTEES)[0]:
            date_lim = remontee_en_cours_bool(REMONTEES)[1]
            keyboard = [
                [
                    InlineKeyboardButton("Modifier la date limite.", callback_data=str(ZERO))
                ],
                [
                    InlineKeyboardButton("Cloturer la remontée.", callback_data=str(ONE))
                ],
                [
                    InlineKeyboardButton("Voir le détail des répondants.", callback_data=str(TWO))
                ],
                [
                    InlineKeyboardButton("Relancer les non-répondants.", callback_data=str(THREE))
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                update.message.reply_text(
                text="Remontée d'information jusqu'au " + date_lim + ".\n\n Nombre de réferents notifiés: nb. \n\n Nombre de réponses recues: nb."
                , reply_markup=reply_markup)
            except:
                query.message.reply_text(
                    text="Remontée d'information jusqu'au " + date_lim + ".\n\n Nombre de réferents notifiés: nb. \n\n Nombre de réponses recues: nb."
                    , reply_markup=reply_markup)
            return ACTION_REMONTEE
        else:
            text = 'Bonjour ' + first_name + ", tu es Administrateur. \n\n Il n'y a pas de remontée en cours"
            keyboard = [
                [
                    InlineKeyboardButton("Demander une une remontée politique", callback_data=str(ZERO)),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                update.message.reply_text(text, reply_markup=reply_markup)
            except:
                query.message.reply_text(text, reply_markup=reply_markup)
            return DEMANDER_REMONTEE
    else:
        try:
            update.message.reply_text("Bonjour "+ first_name + ", il te faut un accès pour m'utiliser.",
                                  reply_markup=ReplyKeyboardRemove(),
                                  )
        except:
            query.message.reply_text("Bonjour " + first_name + ", il te faut un accès pour m'utiliser.",
                                      reply_markup=ReplyKeyboardRemove(),
                                      )
        return ConversationHandler.END

def demander_remontee(update: Update, _: CallbackContext) -> int:
    query = update.callback_query
    query.edit_message_text('Quelle est la date limite de remontée? \n\n Entre la date au format jj/mm/aaaa')
    return VALIDATION_DEMANDE_REMONTEE

def modifier_date_limite(update: Update, _: CallbackContext) -> int:
    query = update.callback_query
    query.edit_message_text('Quelle nouvelle date limite de remontée?')
    return VALIDATION_CHANGEMENT_DATE_REMONTEE

def modification_date_remontee(update: Update, _: CallbackContext) -> int:
    date_input = update.message.text
    if maj_remontee(date_input):
        update.message.reply_text(
            text="J'ai notifié les nb_refs référents qui n'ont pas encore répondu.\n\n Ils ont maintenant jusqu'au " + date_input + " pour faire leur remontée")
    else:
        update.message.reply_text(
            text="Oupsy ! Une erreur est survenue ! Prend un screenshot et envoie a @Victorcohen")
    return ConversationHandler.END

def creation_remontee(update: Update, _: CallbackContext) -> int:
    date_input = update.message.text
    user_id = update.message.from_user.id
    if sauvegarde_remontee(REMONTEES, date_input, 'nouvell_remontee', user_id):
        update.message.reply_text(
            text="J'ai notifié les nb_refs référents qui n'ont pas encore répondu.\n\n Ils ont jusqu'au " + date_input + " pour faire leur remontée")
    else:
        update.message.reply_text(
            text="Oupsy ! Une erreur est survenue ! Prend un screenshot et envoie a @Victorcohen")
    return ConversationHandler.END

def cloture_remontee(update: Update, _: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    keyboard = [
        [
            InlineKeyboardButton("⬅️ Retour", callback_data=str(ZERO))
        ],
        [InlineKeyboardButton("Confirmer", callback_data=str(ONE))
         ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        text="J'avertirais les nb référents qui n'ont pas encore répondu que la remontée est terminée.",
        reply_markup=reply_markup
    )
    return CONFIRMATION_CLOTURE

def sauvegarde_cloture_remontee(update: Update, _: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    date_cloture = date.today().strftime("%d/%m/%Y")
    if maj_remontee(date_cloture):
        query.edit_message_text(
            text="C'est fait!")
    else:
        query.edit_message_text(
            text="Oupsy ! Une erreur est survenue ! Prend un screenshot et envoie a @Victorcohen")
    return ConversationHandler.END

def detail_repondants(update: Update, _: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    keyboard = [
        [
            InlineKeyboardButton("⬅️ Retour", callback_data=str(FOUR))
            ],
        [
            InlineKeyboardButton("Modifier Date Limite", callback_data=str(ZERO))
            ],
        [
            InlineKeyboardButton("Cloturer la remontée", callback_data=str(ONE))
            ],
        [
            InlineKeyboardButton("Relancer les non-répondants", callback_data=str(THREE))
            ]
        ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        text="Ont déjà répondu:\n\n Liste \n\n N'ont pas encore répondu:\n\n Liste", reply_markup=reply_markup
    )
    return ACTION_REMONTEE

def relancer_non_repondants(update: Update, _: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    telegram_bot_sendtext("Message de relance", '1693439153')
    query.edit_message_text(
        text="C'est fait !")
    return ConversationHandler.END


def main() -> None:
    # Create the Updater and pass it your bot's token.
    updater = Updater("1998449664:AAETVJUU7o_7uG7UCELz3bAG6gWZFAUJAF4")

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Add conversation handler with the states GENDER, PHOTO, LOCATION and BIO
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start),
                      CommandHandler('remontee', remontee)],
        states={
            DEMANDER_REMONTEE: [
                CallbackQueryHandler(demander_remontee, pattern='^' + str(ZERO) + '$'),
            ],
            ACTION_REMONTEE: [
                CallbackQueryHandler(modifier_date_limite, pattern='^' + str(ZERO) + '$'),
                CallbackQueryHandler(cloture_remontee, pattern='^' + str(ONE) + '$'),
                CallbackQueryHandler(detail_repondants, pattern='^' + str(TWO) + '$'),
                CallbackQueryHandler(relancer_non_repondants, pattern='^' + str(THREE) + '$'),
                CallbackQueryHandler(remontee, pattern='^' + str(FOUR) + '$'),
            ],
            VALIDATION_DEMANDE_REMONTEE: [
                MessageHandler(Filters.text, creation_remontee),
            ],
            VALIDATION_CHANGEMENT_DATE_REMONTEE: [
                MessageHandler(Filters.text, modification_date_remontee),
            ],
            CONFIRMATION_CLOTURE: [
                CallbackQueryHandler(remontee, pattern='^' + str(ZERO) + '$'),
                CallbackQueryHandler(sauvegarde_cloture_remontee, pattern='^' + str(ONE) + '$'),

            ]
        },
        fallbacks=[CommandHandler('start', start)],
    )

    dispatcher.add_handler(conv_handler)

    # Start the Bot
    updater.start_webhook(listen="0.0.0.0",
                          port=int(PORT),
                          url_path="1998449664:AAETVJUU7o_7uG7UCELz3bAG6gWZFAUJAF4")
    updater.bot.setWebhook('https://manu-online.herokuapp.com/' + "1998449664:AAETVJUU7o_7uG7UCELz3bAG6gWZFAUJAF4")

    updater.idle()


if __name__ == '__main__':
    main()
