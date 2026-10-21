"""Builds faqs.json (2000+ questions) from hand-written topics plus parameterised sets.

Run:  python gen_faqs.py
Each entry: {"question": <phrasing>, "answer": <text>, "canonical": <clean base question>}
Edit the data below to customise the bot for your own product, then re-run.
"""
import json
from pathlib import Path

# --------------------------------------------------------------------------
# 1. Hand-written core FAQs (question, answer)
# --------------------------------------------------------------------------
CORE = [
    # Account
    ("How do I create an account?", "Click 'Sign Up' at the top right, enter your name, email and a password, then confirm your email using the link we send you."),
    ("I forgot my password. How can I reset it?", "Click 'Forgot Password' on the login page and enter your registered email. We will send a reset link that stays valid for 30 minutes."),
    ("How do I change my email address?", "Go to Account > Profile > Email, enter the new address and confirm it with the verification link we send to the new email."),
    ("How can I update my phone number?", "Open Account > Profile, edit the phone number field and verify it with the one-time code sent by SMS."),
    ("How do I delete my account?", "Go to Account > Privacy > Delete Account. Deletion is permanent and removes your order history, saved addresses and reward points after 14 days."),
    ("Why was my account locked?", "Accounts are locked after several failed login attempts or unusual activity. Use 'Forgot Password' to unlock it, or contact support if the problem continues."),
    ("How do I enable two-factor authentication?", "Open Account > Security > Two-Factor Authentication, choose SMS or an authenticator app and follow the on-screen steps."),
    ("Can I have more than one account?", "You can create separate accounts with different email addresses, but reward points and memberships cannot be merged between accounts."),
    ("How do I change my display name?", "Go to Account > Profile, edit your name and press Save. The change appears everywhere within a few minutes."),
    ("How do I log out of all devices?", "Open Account > Security > Active Sessions and choose 'Log out of all devices'. You will need to sign in again on each device."),
    # Orders
    ("How can I track my order?", "Go to 'My Orders' in your account and click 'Track'. You will also receive tracking updates by email and SMS once the order ships."),
    ("How can I cancel my order?", "You can cancel from 'My Orders' before the order ships. After it ships, please refuse delivery or use the return process once it arrives."),
    ("Can I change my delivery address?", "You can change the address from 'My Orders' until the order is shipped. If it has already shipped, contact support and we will try to redirect it."),
    ("Can I change the items in my order after placing it?", "Items cannot be edited after payment. Cancel the order if it has not shipped and place a new one with the right items."),
    ("Where can I find my invoice?", "Open 'My Orders', select the order and click 'Download Invoice'. The invoice is also emailed to you when the order ships."),
    ("Why was my order delayed?", "Delays can come from high order volume, weather, or courier issues. Check the tracking page for the latest status and contact support if the delay is over 3 days."),
    ("My order arrived damaged. What should I do?", "We are sorry about that. Report it within 48 hours from 'My Orders' > 'Report a Problem' with photos of the package and product, and we will send a replacement or refund."),
    ("I received the wrong item. What should I do?", "Open 'My Orders' > 'Report a Problem', choose 'Wrong item' and upload a photo. We will arrange a free pickup and send the correct item."),
    ("Part of my order is missing. What should I do?", "Orders can arrive in more than one package. Check your tracking page, and if a package shows delivered but is missing, report it within 48 hours."),
    ("How do I reorder a previous purchase?", "Open 'My Orders', pick the earlier order and click 'Buy Again' to add the same items to your cart."),
    # Shipping
    ("How long does shipping take?", "Standard shipping takes 3-7 business days and express shipping takes 1-2 business days within the country."),
    ("What shipping options do you offer?", "We offer standard, express and same-day delivery in select cities. Available options and prices are shown at checkout."),
    ("Is there free shipping?", "Yes, standard shipping is free on orders above the free-shipping threshold shown in your cart."),
    ("Do you deliver on weekends?", "Yes, we deliver Monday to Saturday. Sunday delivery is available in selected cities with express shipping."),
    ("Can I pick up my order from a store?", "Store pickup is available in selected cities. Choose 'Pick up in store' at checkout and bring your order confirmation and a photo ID."),
    ("Do you offer same-day delivery?", "Same-day delivery is available in major cities for orders placed before 12 noon on eligible items."),
    ("What happens if I am not home when my order is delivered?", "The courier will try again the next business day, up to three attempts. You can also reschedule from the tracking page."),
    ("Can you ship to a PO box?", "Some couriers cannot deliver to PO boxes. Please use a street address, or contact support to check if your PO box is supported."),
    # Payments
    ("What payment methods do you accept?", "We accept credit and debit cards, UPI, net banking, popular wallets, EMI and cash on delivery on eligible orders."),
    ("Is it safe to enter my card details?", "Yes. Payments are encrypted with industry-standard TLS and processed by PCI-DSS compliant partners. We never store your full card number."),
    ("Why was my payment declined?", "Payments fail because of incorrect details, insufficient balance, bank limits or a failed OTP. Check the details and try again, or use another method."),
    ("I was charged twice. What should I do?", "Duplicate holds usually reverse automatically within 5-7 business days. If both amounts are debited, send us your order number and we will refund the extra charge."),
    ("Can I pay in instalments?", "Yes, EMI is available on eligible cards and orders above the minimum amount. Choose 'EMI' on the payment page to see the plans."),
    ("How do I use a gift card?", "Enter the gift card code in the 'Gift card or coupon' box at checkout. The balance is applied to your order immediately."),
    ("How do I apply a coupon code?", "Paste the coupon code in the 'Coupon code' box in your cart or at checkout and press Apply. Only one coupon can be used per order."),
    ("Why is there a pending charge on my statement?", "Banks place a temporary hold while a payment is verified. It disappears within 3-5 business days if the order did not complete."),
    ("Do you charge GST or other taxes?", "Applicable taxes are included in the price or shown separately at checkout, depending on the product and your location."),
    ("Can I get a GST invoice?", "Yes. Add your GST number in Account > Business Details before ordering and the tax invoice will be generated automatically."),
    # Returns and refunds
    ("What is your return policy?", "Most items can be returned within 30 days of delivery in original condition with tags and packaging. Some categories have shorter windows."),
    ("How long does a refund take?", "Refunds are processed within 5-7 business days after we receive and inspect the returned item."),
    ("How do I start a return?", "Go to 'My Orders', select the item, click 'Return Item', choose a reason and schedule a pickup or drop-off."),
    ("Who pays for return shipping?", "Return shipping is free if the item is defective, damaged or incorrect. For change-of-mind returns, a small pickup fee may apply."),
    ("Can I exchange an item for a different size or colour?", "Yes. Choose 'Exchange' in 'My Orders' within the return window, and we will send the new item once the first one is picked up."),
    ("Will I get my refund on the original payment method?", "Yes, refunds go back to the original payment method. You may also choose store credit, which is added instantly."),
    ("Which items cannot be returned?", "Perishables, personal-care items that are opened, gift cards, and downloadable products cannot be returned."),
    # Products
    ("Are your products genuine?", "Yes. We source directly from brands and authorised distributors, and every product carries the manufacturer's guarantee."),
    ("How do I know if an item is in stock?", "The product page shows 'In stock' or 'Out of stock'. Low stock items display the number of units left."),
    ("Will out-of-stock items be restocked?", "Many are. Click 'Notify me' on the product page and we will email you as soon as it is available again."),
    ("How do I compare two products?", "Tick 'Compare' on up to four products in a listing, then open the Compare tray to see specifications side by side."),
    ("Where can I find the size guide?", "Each clothing and footwear page has a 'Size guide' link below the size selector with measurements in centimetres and inches."),
    ("Do you offer gift wrapping?", "Yes, choose 'Gift wrap' at checkout for a small fee and add a personal message that is printed on a card."),
    ("Do you offer bulk or wholesale discounts?", "Yes. Orders of 10 or more units qualify for bulk pricing. Contact our business team with your requirement for a quote."),
    ("How do I read product reviews?", "Reviews are listed on each product page. Filter by rating or 'Verified purchase' to see feedback from real buyers."),
    # Security and privacy
    ("Is my personal data secure?", "Yes. We use encryption, restricted access and regular audits, and we never sell your personal data to third parties."),
    ("How do I unsubscribe from marketing emails?", "Click 'Unsubscribe' at the bottom of any promotional email or switch off marketing emails in Account > Notifications."),
    ("How can I download my data?", "Go to Account > Privacy > Download my data. We will email you a secure link to your archive within 48 hours."),
    ("Do you use cookies?", "Yes, we use cookies to keep you signed in, remember your cart and improve the site. You can manage them in Cookie Settings."),
    ("How do I report a suspicious email or message?", "Do not click any links. Forward the message to security@example.com and we will investigate."),
    # Membership and rewards
    ("What does the premium membership include?", "Premium includes free express shipping, early access to sales, extra reward points and priority support."),
    ("How do I cancel my membership?", "Go to Account > Membership > Cancel. Your benefits continue until the end of the current billing period."),
    ("How do reward points work?", "You earn points on every purchase. Each point is worth a small discount that you can apply at checkout."),
    ("When do reward points expire?", "Points expire 12 months after they are earned. You can see expiry dates in Account > Rewards."),
    ("How do I refer a friend?", "Share your referral link from Account > Refer & Earn. You both get a reward after your friend's first order."),
    ("Do you offer a student discount?", "Yes. Verify your student status in Account > Student Discount to unlock an extra discount on selected categories."),
    # Support
    ("How do I contact customer support?", "Email support@example.com or call 1800-123-456, Monday to Saturday, 9 AM to 6 PM. You can also use this chat any time."),
    ("What are your customer support hours?", "Phone and chat support are available Monday to Saturday, 9 AM to 6 PM. Email is answered within 24 hours."),
    ("How can I talk to a human agent?", "Call 1800-123-456 or email support@example.com. Chat handoff to an agent is available during support hours."),
    ("How do I give feedback about my experience?", "Use the 'Feedback' link in the website footer or rate your last support interaction. We read every response."),
    ("How do I report a problem with the website?", "Send us a screenshot, your device and browser details at support@example.com so we can fix it quickly."),
    ("Where is your office located?", "Our head office is at 12 Market Street. It is a corporate office, so please contact support instead of visiting for orders."),
    # Offers
    ("When do your big sales happen?", "Our biggest sales run during festive seasons and at the end of each quarter. Follow our newsletter for dates."),
    ("How do I get notified about deals?", "Turn on notifications in Account > Notifications or subscribe to our newsletter to get deal alerts."),
    ("Do you price match?", "If you find the same product cheaper from an authorised seller, send us the link within 7 days of ordering and we will review a price adjustment."),
]

# --------------------------------------------------------------------------
# 2. Parameterised sets
# --------------------------------------------------------------------------
TIERS = {
    (3, 5, 1, 2): ["India", "Nepal", "Bangladesh", "Sri Lanka", "Bhutan"],
    (5, 8, 2, 4): ["the UAE", "Singapore", "Malaysia", "Thailand", "Indonesia", "Japan",
                   "South Korea", "Saudi Arabia", "Qatar", "Australia"],
    (8, 14, 3, 6): ["the United States", "Canada", "the United Kingdom", "Germany", "France",
                    "Italy", "Spain", "the Netherlands", "Brazil", "Mexico", "South Africa",
                    "Nigeria", "Kenya", "New Zealand", "Ireland", "Sweden", "Switzerland",
                    "Turkey", "Egypt", "the Philippines", "Vietnam", "Portugal", "Norway",
                    "Poland", "Argentina"],
}

PAYMENTS = {
    "Visa": True, "Mastercard": True, "American Express": True, "RuPay": True, "UPI": True,
    "Google Pay": True, "PhonePe": True, "Paytm": True, "Apple Pay": True, "PayPal": True,
    "net banking": True, "cash on delivery": True, "EMI": True, "gift cards": True,
    "store credit": True, "Bitcoin": False, "bank transfer": False, "cheque": False,
}

CATEGORIES = {
    "laptops": (10, "a 1-year manufacturer warranty"),
    "smartphones": (7, "a 1-year manufacturer warranty on the device and 6 months on accessories"),
    "headphones": (10, "a 1-year manufacturer warranty"),
    "smartwatches": (10, "a 1-year manufacturer warranty"),
    "cameras": (10, "a 1-year manufacturer warranty"),
    "tablets": (10, "a 1-year manufacturer warranty"),
    "gaming consoles": (7, "a 1-year manufacturer warranty"),
    "kitchen appliances": (15, "a 1-year warranty against manufacturing defects"),
    "furniture": (15, "a 1-year warranty against manufacturing defects"),
    "shoes": (30, "no manufacturer warranty, but manufacturing defects are covered for 30 days"),
    "clothing": (30, "no manufacturer warranty, but manufacturing defects are covered for 30 days"),
    "backpacks": (30, "a 6-month warranty against manufacturing defects"),
    "books": (7, "no warranty, but damaged or misprinted copies are replaced within 7 days"),
    "toys": (15, "no warranty, but defective items are replaced within 15 days"),
    "beauty products": (7, "no warranty, and only unopened products can be returned"),
    "home decor": (15, "no warranty, but items damaged in transit are replaced"),
}

DEVICES = ["an Android phone", "an iPhone", "a Windows laptop", "a Mac", "an iPad",
           "Google Chrome", "Mozilla Firefox", "Safari", "Microsoft Edge", "a tablet"]

ISSUES = [
    ("Why is the website not loading on {d}?",
     "If the site does not load on {d}, check your internet connection, clear the cache and cookies, update the browser or system, and try again. If it still fails, switch networks and contact support with a screenshot."),
    ("Why can't I log in on {d}?",
     "If login fails on {d}, check your email and password, reset your password if needed, and make sure cookies are enabled. Clearing the cache or trying a private window often helps."),
    ("Why does the checkout page freeze on {d}?",
     "If checkout freezes on {d}, refresh the page, disable ad blockers or extensions, and update the browser or system. Your cart is saved, so you will not lose items."),
    ("Why are images not showing on {d}?",
     "If images are missing on {d}, check your connection, turn off data-saver mode, clear the cache and reload the page."),
    ("Why am I not getting the OTP on {d}?",
     "If the OTP does not arrive on {d}, check signal and spam filters, wait 60 seconds, and press 'Resend OTP'. Make sure the phone number on your account is correct."),
    ("Why does payment fail on {d}?",
     "If payment fails on {d}, confirm your card or UPI details, allow pop-ups for the bank page, and try again. Using another payment method or device also helps."),
    ("Why is the chat not working on {d}?",
     "If chat does not work on {d}, reload the page, check your connection, and make sure JavaScript is enabled. You can also email support@example.com."),
]

# --------------------------------------------------------------------------
# 3. Build entries
# --------------------------------------------------------------------------
def base_pairs():
    pairs = list(CORE)

    for (std_lo, std_hi, exp_lo, exp_hi), names in TIERS.items():
        for c in names:
            ship = (f"Yes, we ship to {c}. Standard delivery takes {std_lo}-{std_hi} business days and "
                    f"express takes {exp_lo}-{exp_hi} business days. Import duties or taxes may apply on arrival.")
            cost = (f"Shipping charges for {c} depend on weight and delivery speed, and are shown at checkout "
                    f"before you pay. Qualifying orders get free standard shipping.")
            pairs += [
                (f"Do you ship to {c}?", ship),
                (f"Is delivery available in {c}?", ship),
                (f"How long does delivery to {c} take?", ship),
                (f"What are the shipping charges for {c}?", cost),
            ]

    for m, ok in PAYMENTS.items():
        if ok:
            ans = (f"Yes, you can pay with {m} at checkout. Choose it on the payment page; "
                   f"some methods may have a minimum or maximum order value.")
        else:
            ans = (f"Sorry, we do not accept {m}. You can pay with cards, UPI, net banking, "
                   f"wallets, EMI or cash on delivery.")
        pairs += [
            (f"Do you accept {m}?", ans),
            (f"Can I pay using {m}?", ans),
            (f"Is {m} available as a payment option?", ans),
        ]

    for cat, (window, warranty) in CATEGORIES.items():
        pairs += [
            (f"What is the return policy for {cat}?",
             f"{cat.capitalize()} can be returned within {window} days of delivery in original condition with all accessories and packaging."),
            (f"Do {cat} come with a warranty?", f"{cat.capitalize()} come with {warranty}."),
            (f"Can I exchange {cat}?",
             f"Yes, {cat} can be exchanged within {window} days for the same item or a different variant, subject to availability."),
            (f"How do I choose the right {cat}?",
             f"Use the filters on the {cat} page, compare up to four products side by side, and read verified reviews. Our chat can also suggest options for your budget."),
        ]

    for d in DEVICES:
        for q, a in ISSUES:
            pairs.append((q.format(d=d), a.format(d=d)))

    return pairs


WRAPPERS = [
    "{q}",
    "Hi, {l}",
    "Please tell me: {l}",
    "I would like to know: {l}",
    "Quick question: {l}",
    "Could you let me know: {l}",
]


def lower_first(q):
    if q.startswith(("I ", "I'")):
        return q
    return q[0].lower() + q[1:]


def main():
    seen, entries = set(), []
    for q, a in base_pairs():
        for w in WRAPPERS:
            text = w.format(q=q, l=lower_first(q))
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            entries.append({"question": text, "answer": a, "canonical": q})

    assert len(entries) >= 2000, f"Only {len(entries)} questions generated"
    out = Path(__file__).with_name("faqs.json")
    out.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {len(entries)} questions ({len(base_pairs())} base topics) to {out.name}")


if __name__ == "__main__":
    main()
