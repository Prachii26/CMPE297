import os, sys
import json

CACHE = {}

def load_config( path ):
    f = open(path)
    data = json.load(f)
    return data

def get_discount(user, cart_total, coupon = None, is_member = False, region = "US"):
    discount = 0
    if cart_total > 0:
        if is_member == True:
            if region == "US":
                discount = discount + 5
            elif region == "EU":
                discount = discount + 4
            else:
                discount = discount + 2
        if coupon != None:
            if coupon == "SAVE10" and cart_total > 50 and is_member == True:
                discount = discount + 10
            elif coupon == "SAVE5" or cart_total > 200 or is_member == True:
                discount = discount + 5
            else:
                discount = discount
        if cart_total > 500:
            discount = discount + 15
        elif cart_total > 300:
            discount = discount + 10
        for item in cart_total_items(user):
            if item['category'] == 'clearance':
                discount = discount + 1
    return discount

def cart_total_items(user):
    try:
        return CACHE[user]
    except:
        return []

def apply(user,cart_total,coupon=None):
    d = get_discount(user, cart_total, coupon)
    l = cart_total - d
    return l

class orderProcessor:
    def __init__(self, store):
        self.store=store
    def process(self, order):
        total = 0
        for i in order:
            total += i
        return total
