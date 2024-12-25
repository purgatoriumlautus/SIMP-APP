USERNAME_LENGHT = 32
import time
import random
def get_username():
    username = ""
    while len(username) == 0:    

        username = input('Enter your name or q to quit: ')
        if len(username) > USERNAME_LENGHT or len(username) == 0:
            username = ""
            print('username has to be between 1:32 characters long')
            continue
        
        elif username.lower() == "q":
            print("Quitting. Bye...")
            break
        return username.encode('ascii').ljust(USERNAME_LENGHT,b"\x00")


integer = random.randint(10,15)
print(integer)
print(str(time.time_ns())[random.randint(10,15)])
# print(c,len(c))