from telegram.ext import Updater,CommandHandler,MessageHandler, Filters, RegexHandler, ConversationHandler,CallbackQueryHandler
from telegram import InlineQueryResultArticle, InputTextMessageContent, ParseMode
import os
from functools import wraps
import logging
import pickle
import redis
from datetime import datetime
import pandas as pd
from plotnine import *

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

def loadAlert(userID):
    try:
        filename = userID+'alert'
        alert = pickle.loads(r.get(filename))
        print("loaded alerts")
        return alert
    except:
        print("did not load alerts")
        return {}

def loadDF(userID):
    db = loadDB(userID)
    if any(db):
        df = pd.DataFrame.from_dict(db)
        df['Tag'] = pd.DatetimeIndex(df['Zeit']).day
        df['Monat'] = pd.DatetimeIndex(df['Zeit']).month
        df['Jahr'] = pd.DatetimeIndex(df['Zeit']).year
        df['Type'] = df['Type'].str.lower()
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
ACCOUNT, NEW_ACCOUNT, EXPENSE, SAVED, TAG, ALERT, DELETE = range(7)
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
    user_id = str(update.effective_user.id)
    try:
        alert = loadAlert(user_id)
        df = loadDF(user_id)
    except:
        print("Could not load alerts")
        context.bot.send_message(chat_id=update.message.chat_id, text="Noch keine Daten.")
        return ConversationHandler.END
    alert_sum = df.loc[df['Type'] == context.user_data['Type']]['Betrag'].sum()
    print(alert_sum)
    print(alert[context.user_data['Type']])
    alert_delta = alert[context.user_data['Type']]-alert_sum
    print(alert_delta)
    if alert_delta in range(0,21):
        print('Near limit')
        alert_text = 'Achtung, nur noch ' + str(alert_delta) + '€ in der Kategorie ' + str(context.user_data['Type']) + ' bis zu deinem Limit diesen Monat!'
        update.message.reply_text(alert_text)
        return ConversationHandler.END
    elif alert_delta < 0:
        print('Below limit')
        alert_text = 'Achtung, du hast dein Limit um ' + str(-1*alert_delta) + '€ in der Kategorie ' + str(context.user_data['Type']) + ' diesen Monat überschritten!'
        update.message.reply_text(alert_text)
        return ConversationHandler.END
    else:
        print('Not above limit')
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
dispatcher.add_handler(conv_handler,group = 1)


# tag alert handler

@restricted #user restriction
def set_alert(update,context):
    update.message.reply_text('Ich zeichne jetzt gerne ein Limit für deine Ausgabe auf, solltest du dies abbrechen wollen kannst du jederzeit /cancel eingeben.')
    update.message.reply_text('Für welchen Ausgabentyp möchtest Du ein Limit setzen oder verändern? (Typ, für die Liste vorhandener Typen siehe /tags)')
    return TAG #Asks for type of expense to save

@restricted
def tag_alert(update,context):
    tag = str(update.message.text)
    tag = tag.lower()
    tag = tag.strip()
    user_id = str(update.effective_user.id)
    db = loadDB(user_id)
    if  any(db):
        tags = [x['Type'] for x in db if x]
        tags = [x.lower() for x in tags]
        tags = [x.strip() for x in tags]
        tags.sort()
        if tag in tags:
            # save selection into user data
            context.user_data['Type_alert']=tag
            update.message.reply_text('Und wie hoch soll Dein monatliches Limit sein?')
            return ALERT
        else:
            update.message.reply_text('Diesen Ausgabentyp kenne ich nicht, versuche es noch einmal. (Für die Liste vorhandener Typen siehe /tags)')
            return TAG
    else:
        update.message.reply_text('Du hast noch keine Ausgabentypen. Aufzeichnung wird abgebrochen.')
        return ConversationHandler.END # Sets an alert for an expense type

@restricted
def saved_alert(update,context):
    limit = str(update.message.text)
    try:
        limit = float(limit.replace(',','.'))
    except:
        update.message.reply_text('Eingabe ist keine Zahl,der Eintrag wurde nicht gespeichert!')
        return ConversationHandler.END
    # save selection into user data
    context.user_data['alert_limit'] = limit
    alert_entry = {
        context.user_data['Type_alert']:context.user_data['alert_limit']
    }
    # Load/create pickle and add new record, afterwards save pickle
    try:
        user_id = str(update.effective_user.id)
        filename = user_id+'alert'
        alert = loadAlert(user_id)
        alert.update(alert_entry)
        palert = pickle.dumps(alert)
        r.set(filename,palert)
        print('saved in old')
        print(alert)
    except:
        user_id = str(update.effective_user.id)
        filename = user_id+'alert'
        alert = alert_entry
        palert = pickle.dumps(alert)
        r.set(filename,palert)
        print('saved in new')
        print(alert)
    
    update.message.reply_text('Gespeichert!')
    return ConversationHandler.END

alert_handler = ConversationHandler(
        entry_points=[CommandHandler('limit', set_alert)],
        states={
            TAG: [MessageHandler(Filters.text,tag_alert)],
            ALERT: [MessageHandler(Filters.text,saved_alert)],
            },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
dispatcher.add_handler(alert_handler,group = 2)

# delete and edit handlers
@restricted
def set_delete(update, context):
    user_id = str(update.effective_user.id)
    df = loadDF(user_id)
    try:
        df['Zeit'] = df['Zeit'].dt.strftime('%d/%m/%y')
        last_5 = df.tail(5).iloc[:,1:4].to_string(index = True,col_space = 9)
        context.bot.send_message(chat_id=update.message.chat_id, text=last_5)
        context.bot.send_message(chat_id=update.message.chat_id, text='Welchen dieser Einträge möchtest Du löschen, antworte bitte mit der Index-Nummer.')
        return DELETE
    except:
        context.bot.send_message(chat_id=update.message.chat_id, text="Noch keine Daten.")
        return ConversationHandler.END

@restricted
def delete_entry(update,context):
    try:
        delete = int(update.message.text)
    except:
        update.message.reply_text('Eingabe ist keine Zahl,bitte gibt eine Index-Zahl ein!')
        return DELETE
    # Load/create pickle and add new record, afterwards save pickle
    try:
        user_id = str(update.effective_user.id)
        db = pickle.loads(r.get(user_id))
        del db[delete]
        pdb = pickle.dumps(db)
        r.set(user_id,pdb)
    except:
        update.message.reply_text('Es gibt noch keine Einträge zu löschen!')
        return ConversationHandler.END
    update.message.reply_text('Entfernt!')
    return ConversationHandler.END 


delete_handler = ConversationHandler(
        entry_points=[CommandHandler('entfernen', set_delete)],
        states={
            DELETE: [MessageHandler(Filters.text,delete_entry)],
            },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
dispatcher.add_handler(delete_handler,group = 3)

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
    else:
        context.bot.send_message(chat_id=update.message.chat_id, text="Noch keine Daten.")

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
    except:
        print('Proper except return')
        context.bot.send_message(chat_id=update.message.chat_id, text="Noch keine Daten.")

overview_handler = CommandHandler("report", overview)
dispatcher.add_handler(overview_handler)

@restricted
def sum_typ(update, context):
    user_id = str(update.effective_user.id)
    df = loadDF(user_id)
    try:
        summe = df.groupby(['Type'])['Betrag'].sum().to_string()
        context.bot.send_message(chat_id=update.message.chat_id, text=summe)
    except:
        print('Proper except return')
        context.bot.send_message(chat_id=update.message.chat_id, text="Noch keine Daten.")


typsum_handler = CommandHandler("typ", sum_typ)
dispatcher.add_handler(typsum_handler)

@restricted
def plot_typ(update, context):
    user_id = str(update.effective_user.id)
    df = loadDF(user_id)
    df = df.loc[df['Jahr'] == datetime.now().year]
    df = df.loc[df['Monat'] >= (datetime.now().month-3)]
    df['Monatsname'] = df['Zeit'].dt.month_name()
    benutzte = df['Monatsname'].tolist()
    Monatsnamen =['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    Monatsnamen =  [x for x in Monatsnamen if x in benutzte]
    df['Monat'] = pd.Categorical(df['Monatsname'], categories=Monatsnamen)
    pdf = df.groupby(['Monat','Type'])['Betrag'].sum().reset_index(name='Betrag').round(1)
    p = (ggplot(pdf, aes(x = 'Monat', y = 'Betrag',fill='Type')) + geom_col(position='dodge') + geom_text(aes(label = 'Betrag', group = 'Type'),position = position_dodge(width = 0.9),size = 10))  + coord_flip() + labs(Y = 'Betrag in €', x = 'Monat', title = 'Ausgaben je Typ über die letzten drei Monate')
    p.save(filename = 'month_plot.png', height=4, width=6, units = 'in', dpi=100)
    context.bot.send_photo(chat_id=update.message.chat_id,photo = open('month_plot.png', 'rb'))


plot_handler = CommandHandler("plot", plot_typ)
dispatcher.add_handler(plot_handler)

#Unknown commands handler
@restricted
def unknown(update, context):
    command = str(update.message.text)
    allowed = ['/ausgabe','/limit','/cancel','/entfernen']
    if command in allowed:
        pass
    else:
        context.bot.send_message(chat_id=update.message.chat_id, text="Diesen Befehl gibt es nicht, bitte benutze das Command-Menü unten rechts.")

unknown_handler = MessageHandler(Filters.command, unknown)
dispatcher.add_handler(unknown_handler)

#Start webhook
updater.start_webhook(listen="0.0.0.0",
                    port=PORT,
                    url_path=TELEGRAM_TOKEN)
updater.bot.set_webhook("https://flexpense.herokuapp.com/" + TELEGRAM_TOKEN)
updater.idle()
