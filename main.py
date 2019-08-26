from telegram.ext import Updater,CommandHandler,MessageHandler, Filters, RegexHandler, ConversationHandler,CallbackQueryHandler
from telegram import InlineQueryResultArticle, InputTextMessageContent, ParseMode
import os
from functools import wraps
import logging
import pickle
import redis
from datetime import datetime
import pandas as pd

LIST_OF_ADMINS = [961108390]
TELEGRAM_TOKEN = "936719065:AAEtWah8YV4x_68CFxXkOeJGvbsk5KukyrI"
entry = {}
r = redis.from_url(os.environ.get("REDIS_URL"))

PORT = int(os.environ.get('PORT', '8443'))
updater = Updater(TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',level=logging.INFO)

# general functions

def loadDB(userID):
    try:
        db = pickle.loads(r.get(userID))
        print("loaded db")
        return db
    except:
        print("did not load db")
        return {}

def loadDF(userID):
    db = loadDB(userID)
    if any(db):
        df = pd.DataFrame.from_dict(db)
        df['Tag'] = pd.DatetimeIndex(df['Zeit']).day
        df['Monat'] = pd.DatetimeIndex(df['Zeit']).month
        df['Jahr'] = pd.DatetimeIndex(df['Zeit']).year
        df['Betrag'] = pd.to_numeric(df['Betrag'])
        print('DF returned')
        return df
    else:
        df = False
        print('No DF')
        return df

# usage restriction

def restricted(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in LIST_OF_ADMINS:
            print("Unauthorized access denied for {}. This is a private bot, the droids you are looking for are not here.".format(user_id))
            return
        return func(update, context, *args, **kwargs)
    return wrapped

# Primary saving handler
ACCOUNT, NEW_ACCOUNT, EXPENSE, SAVED = range(4)
#ACCOUNT, EXPENSE, SAVED = range(3)

@restricted
def start(update, context):
    context.bot.send_message(chat_id = update.message.chat_id, text="Hallo Lara und Fabian, dies ist euer privater Ausgabentracker :)")
    print(update.message.from_user.id)

start_handler = CommandHandler("start",start)
dispatcher.add_handler(start_handler)

@restricted #user restriction
def ausgabe(update,context):
    update.message.reply_text('Ich zeichne jetzt gerne deine Ausgabe auf, solltest du dies abbrechen wollen kannst du jederzeit /cancel eingeben.')
    update.message.reply_text('Was für eine Ausgabe möchest Du heute speichern? (Typ, für die Liste vorhandener Typen siehe /tags)')
    return ACCOUNT #Asks for type of expense to save

@restricted
def account(update,context):
    print(ACCOUNT)
    account = str(update.message.text)
    account = account.lower()
    account = account.strip()
    user_id = str(update.effective_user.id)
    db = loadDB(user_id)
    if  any(db):
        tags = [x['Type'] for x in db if x]
        tags = [x.lower() for x in tags]
        tags = [x.strip() for x in tags]
        tags.sort()
        if account in tags:
            # save selection into user data
            context.user_data['Type']=account
            update.message.reply_text('Und wieviel Geld hast Du ausgegeben?(Betrag)')
            return EXPENSE # saves type of expense and ask for expense amount
        else:
            update.message.reply_text('Dies ist ein neuer Ausgabentyp, wenn Du ihn wirklich neu anlegen willst wiederhole die Eingabe, wenn nicht dann antworte "NEIN"')
            return NEW_ACCOUNT
    else:
        # save selection into user data
        context.user_data['Type']=account
        update.message.reply_text('Und wieviel Geld hast Du ausgegeben?(Betrag)')
        return EXPENSE # saves type of expense and ask for expense amount

@restricted
def new_account(update,context):
    approval = update.message.text
    approval = approval.strip()
    if  approval == 'NEIN':
        update.message.reply_text('Der Vorgang wird abgebrochen')
        return ConversationHandler.END
    else:
        approval = approval.lower()
        context.user_data['Type']=approval
        update.message.reply_text('Und wieviel Geld hast Du ausgegeben?(Betrag)')
        return EXPENSE

@restricted
def expense(update,context):
    expense = str(update.message.text)
    try:
        expense = float(expense.replace(',','.'))
    except:
        update.message.reply_text('Eingabe ist keine Zahl,der Eintrag wurde nicht gespeichert!')
        return ConversationHandler.END
    # save selection into user data
    context.user_data['Betrag']=expense
    entry = {
        "ID" : update.effective_user.id,
        "Zeit" : update.message.date,
        "Type" : context.user_data['Type'],
        "Betrag" : context.user_data['Betrag']
    }
    # Load/create pickle and add new record, afterwards save pickle
    try:
        user_id = str(update.effective_user.id)
        db = pickle.loads(r.get(user_id))
        db.append(entry)
        pdb = pickle.dumps(db)
        r.set(user_id,pdb)
    except:
        user_id = str(update.effective_user.id)
        db = list()
        db.append(entry)
        pdb = pickle.dumps(db)
        r.set(user_id,pdb)
    
    update.message.reply_text('Gespeichert!')
    return ConversationHandler.END

@restricted
def cancel(update,context):
    update.message.reply_text('Du hast die Eingabe abgebrochen.')
    return ConversationHandler.END

conv_handler = ConversationHandler(
        entry_points=[CommandHandler('ausgabe', ausgabe)],
        states={
            ACCOUNT: [MessageHandler(Filters.text,account)],
            NEW_ACCOUNT: [MessageHandler(Filters.text,new_account)],
            EXPENSE: [MessageHandler(Filters.text,expense)],
            },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
dispatcher.add_handler(conv_handler)


# reporting handlers
@restricted
def show_last(update, context):
    user_id = str(update.effective_user.id)
    df = loadDF(user_id)
    try:
        df['Zeit'] = df['Zeit'].dt.strftime('%d/%m/%y')
        last_5 = df.tail(5).iloc[:,1:4].to_string(index = False,col_space = 9)
        context.bot.send_message(chat_id=update.message.chat_id, text=last_5)
        return ConversationHandler.END
    except:
        context.bot.send_message(chat_id=update.message.chat_id, text="Noch keine Daten.")
        return ConversationHandler.END

last_handler = CommandHandler("letzte", show_last)
dispatcher.add_handler(last_handler)

@restricted
def show_tags(update, context):
    user_id = str(update.effective_user.id)
    db = loadDB(user_id)
    if  any(db):
        tags = [x['Type'] for x in db if x]
        tags = [x.lower() for x in tags]
        tags.sort()
        tags = set(tags)
        tags = ', '.join(tags)
        print(tags)
        context.bot.send_message(chat_id=update.message.chat_id, text=tags)
        if ACCOUNT:
            cancel()
    else:
        context.bot.send_message(chat_id=update.message.chat_id, text="Noch keine Daten.")
        if ACCOUNT :
            cancel()

tag_handler = CommandHandler("tags", show_tags)
dispatcher.add_handler(tag_handler)

@restricted
def overview(update, context):
    user_id = str(update.effective_user.id)
    df = loadDF(user_id)
    try:
        monat = df.loc[df['Monat'] == datetime.now().month]
        jahr = df.loc[df['Jahr'] == datetime.now().year]
        monat_sum = monat['Betrag'].sum()
        jahr_sum = jahr['Betrag'].sum()
        overview = 'Diesen Monat hast Du ' + str(monat_sum) + '€ ausgegeben und dieses Jahr bislang ' + str(jahr_sum) + '€'
        context.bot.send_message(chat_id=update.message.chat_id, text=overview)
        return ConversationHandler.END
    except:
        print('Proper except return')
        context.bot.send_message(chat_id=update.message.chat_id, text="Noch keine Daten.")
        return ConversationHandler.END

overview_handler = CommandHandler("report", overview)
dispatcher.add_handler(overview_handler)

@restricted
def sum_typ(update, context):
    user_id = str(update.effective_user.id)
    df = loadDF(user_id)
    try:
        summe = df.groupby(['Type'])['Betrag'].sum().to_string()
        context.bot.send_message(chat_id=update.message.chat_id, text=summe)
        return ConversationHandler.END
    except:
        print('Proper except return')
        context.bot.send_message(chat_id=update.message.chat_id, text="Noch keine Daten.")
        return ConversationHandler.END

typsum_handler = CommandHandler("typ", sum_typ)
dispatcher.add_handler(typsum_handler)

#Unknown commands handler
@restricted
def unknown(update, context):
    context.bot.send_message(chat_id=update.message.chat_id, text="Diesen Befehl gibt es nicht, bitte benutze das Command-Menü unten rechts.")
    return ConversationHandler.END

unknown_handler = MessageHandler(Filters.command, unknown)
dispatcher.add_handler(unknown_handler)

#Start webhook
updater.start_webhook(listen="0.0.0.0",
                    port=PORT,
                    url_path=TELEGRAM_TOKEN)
updater.bot.set_webhook("https://flexpense.herokuapp.com/" + TELEGRAM_TOKEN)
updater.idle()
