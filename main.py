import sys
import threading
from threading import *
import json
import socket
import netifaces as ni
import time
import select
import os
import bisect
import base64
from ebook import open_book
from datetime import datetime, timedelta

PORT = 12345
BUFFER_SIZE = 10240
HOSTNAME = socket.gethostname()
x = ni.gateways()
y = x['default'][2][1]
LOCAL_IP = ni.ifaddresses(y)[ni.AF_INET][0]['addr']
TYPE1_DICT_HEAD = {"type": 1, "name": HOSTNAME, "IP": LOCAL_IP}
TYPE2_DICT = {"type": 2, "name": HOSTNAME, "IP": LOCAL_IP}
TYPE2_JSTR = json.dumps(TYPE2_DICT).encode("utf-8")
ACKS = {}
CHARS = {}
RECEIVED = []
contacts = {}
contact_names = []
responded_stamps = []
READING_SPEED = .1
escape = True


def discover():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        timestamp = int(time.time())
        TYPE1_DICT = TYPE1_DICT_HEAD
        TYPE1_DICT["ID"] = timestamp
        TYPE1_JSTR = json.dumps(TYPE1_DICT).encode("utf-8")
        for i in range(10):
            s.sendto(TYPE1_JSTR, ('<broadcast>', PORT))


def print_char(char):
    print_cyan(char)

def listen_udp():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('', PORT))
        result = select.select([s], [], [])
        while True:
            received = result[0][0].recv(BUFFER_SIZE)
            decoded = received.decode("utf-8")
            data_json = json.loads(decoded)
            if data_json["type"] == 1:
                if data_json["ID"] not in responded_stamps \
                        and data_json["IP"] != LOCAL_IP \
                        and data_json["name"] not in contact_names:
                    responded_stamps.append(data_json["ID"])
                    contacts[data_json["name"]] = data_json["IP"]
                    contact_names.append(data_json["name"])
                    destination_ip = data_json["IP"]
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        try:
                            s.connect((destination_ip, PORT))
                            s.sendall(TYPE2_JSTR)
                        except:
                            pass
            elif data_json["type"] == 4:
                char = data_json["body"]
                sender_name = data_json["name"]
                sender_ip = contacts[sender_name]
                timestamp = data_json["timestamp"]
                time_to_show = datetime.strptime(data_json["time_to_show"], '%Y-%m-%d %H:%M:%S.%f')

                if timestamp not in RECEIVED:
                    delay = (time_to_show - datetime.now()).total_seconds()
                    threading.Timer(delay, print_char, [char]).start()
                    RECEIVED.append(timestamp)

                for i in range(10):
                    send_ack(sender_ip, timestamp)

            elif data_json["type"] == 5:
                timestamp = data_json["timestamp"]
                ACKS[timestamp] = True


def send_ack(recipient_ip, timestamp):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(type5_wrapper(timestamp), (recipient_ip, PORT))


def print_red(*message):
    print('\033[91m' + " ".join(message) + '\033[0m')


def print_green(*message):
    print('\033[92m' + " ".join(message) + '\033[0m')


def print_yellow(*message):
    print('\033[93m' + " ".join(message) + '\033[0m')


def print_cyan(*message):
    print('\033[96m' + " ".join(message) + '\033[0m', flush=True, end="")


def listen_tcp():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((LOCAL_IP, PORT))
        while True:
            s.listen()
            received = b''
            conn, addr = s.accept()
            with conn:
                while True:
                    data = conn.recv(BUFFER_SIZE)
                    received += data
                    if not data:
                        break

            decoded = received.decode("utf-8")
            data_json = json.loads(decoded)

            if data_json["type"] == 2:
                contacts[data_json["name"]] = data_json["IP"]
                contact_names.append(data_json["name"])

            elif data_json["type"] == 3:
                print_red(data_json["name"] + ": " + data_json["body"])


def type3_wrapper(message):
    msg_dict = {"type": 3, "name": HOSTNAME, "body": message}
    msg_jstr = json.dumps(msg_dict).encode("utf-8")
    return msg_jstr


def type4_wrapper(char, now):
    timestamp = now.timestamp()
    CHARS[timestamp] = char
    time_to_show = now + timedelta(milliseconds=100)
    msg_dict = {"type": 4, "name": HOSTNAME, "body": char, "timestamp": timestamp, "time_to_show": time_to_show}
    msg_jstr = json.dumps(msg_dict, default=str).encode("utf-8")
    return msg_jstr


def write(message, recipient):
    global escape
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((contacts["{}".format(recipient)], PORT))
            s.sendall(type3_wrapper(message))
        except (KeyError, ConnectionRefusedError):
            contacts.pop(recipient)
            contact_names.remove(recipient)
            print_yellow("{} seems to have gone offline. Returning to the main menu.".format(recipient))
            escape = False
    return


def display_contacts():
    if not contacts.keys():
        print_yellow("There are no online contacts.")
        return
    for key in contacts.keys():
        print_yellow(key)


def chat(recipient):
    global escape
    print_yellow("chatting with", recipient)
    print_yellow("(type --exit to exit a chat)")

    while escape:
        msg = input()
        if msg == "--exit":
            return
        else:
            write(msg, recipient)
    escape = True


def type5_wrapper(timestamp):
    msg_dict = {"type": 5, "name": HOSTNAME, "timestamp": timestamp}
    msg_jstr = json.dumps(msg_dict).encode("utf-8")
    return msg_jstr


def read_book(book, recipient_ip):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        for char in book:
            timestamp = datetime.now()
            msg = type4_wrapper(char, timestamp)
            for i in range(10):
                s.sendto(msg, (recipient_ip, PORT))
            delay = (timestamp + timedelta(milliseconds=100) - datetime.now()).total_seconds()
            threading.Timer(delay, print_char, [char]).start()
            time.sleep(READING_SPEED)


def main_menu():
    while True:
        try:
            print_green("What would you like to do?")
            print_green("contacts: see online contacts")
            print_green("chat: start a chat with a user")
            print_green("quit: exit the program")
            print_green("read: read with someone")
            inp = input()

            if inp == 'contacts':
                display_contacts()

            elif inp == 'quit':
                try:
                    print_yellow("Goodbye.")
                    sys.exit()
                except KeyError:
                    print_yellow("Goodbye.")
                    sys.exit()

            elif inp == 'read':
                print_green("Who would you like to read with?")
                inp = input()
                while inp not in contact_names:
                    print_yellow("Please enter the name of an online user, or type --exit to return to the main menu.")
                    inp = input()

                    if inp == '--exit':
                        break


                if inp != '--exit':
                    recipient_ip = contacts[inp]
                    print_yellow("Please enter the absolute path of the epub file you would like to read.")
                    pathinp = input()
                    book = open_book(pathinp)
                    read_book(book, recipient_ip)

            elif inp == 'chat':
                print_green("Who would you like to chat with?")
                inp = input()
                while inp not in contact_names:
                    print_yellow("Please enter the name of an online user, or type --exit to return to the main menu.")
                    inp = input()

                    if inp == '--exit':
                        break

                if inp != '--exit':
                    chat(inp)

                while inp not in contact_names:
                    print_yellow("Please enter the name of an online user, or type --exit to return to the main menu.")
                    inp = input()

                    if inp == '--exit':
                        break

                if inp != '--exit':
                    chat(inp)

            else:
                print_yellow("Invalid input.")
        except KeyboardInterrupt:
            main_menu()


def main():
    listener_daemon = Thread(target=listen_tcp)
    listener_daemon.setDaemon(True)
    listener_daemon.start()

    udp_listener_daemon = Thread(target=listen_udp)
    udp_listener_daemon.setDaemon(True)
    udp_listener_daemon.start()
    discover()

    main_menu()


if __name__ == "__main__":
    main()
