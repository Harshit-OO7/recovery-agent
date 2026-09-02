""""Synthetic Dataset Generator for Post-Checkout Payment Failures.

ARCHITECTURAL PRINCIPLES APPLIED:
1. Ground-Truth Encapsulation:
   The `propensity_profile` namespace is strictly for the customer behavior simulator.
   In real production e-commerce, the merchant never has a direct label for the customer's true
   psychological intent (reliable, distracted, hesitant, broke, ghost).
   Exposing it to the agent would cause target leakage and invalidate our evaluation metrics.
2. Determinism:
   All generation uses a seed-locked random instance (random.Random(seed)). The exact same seed
   produces byte-identical records across runs.
3. Realistic Retail Distribution:
   - Plausible Indian e-commerce cart summaries and realistic Razorpay error responses.
   - Micro-transactions (< Rs 100) to trigger cost-of-contact stopping rules.
   - Explicit risk-flagged cohort to test fraud/dispute suppression gates.
   - 60/20 Train vs. Held-Out evaluation split.
"""

import argparse
import random
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Dict

from app.config import settings
from app.db import Base, engine, SessionLocal
from app.models.enums import (
    PropensityProfile,
    PaymentMethod,
    PaymentStatus,
    DatasetSplit,
)
from app.models.customer import Customer
from app.models.failed_payment import FailedPayment


INDIAN_FIRST_NAMES = [
    "Aarav", "Aditi", "Amit", "Ananya", "Arjun", "Deepak", "Divya", "Gaurav",
    "Harshit", "Ishaan", "Kavita", "Manish", "Meera", "Neha", "Nikhil", "Pooja",
    "Pranav", "Priya", "Rahul", "Rhea", "Rohan", "Sanjay", "Shreya", "Siddharth",
    "Sneha", "Tanvi", "Varun", "Vikas", "Vikram", "Yash", "Aakash", "Bhavna",
    "Chirag", "Deepika", "Esha", "Farhan", "Gayatri", "Hemant", "Indu", "Jayesh",
    "Karan", "Lavanya", "Mohit", "Nandini", "Omkar", "Payal", "Rajesh", "Sameer",
    "Tarun", "Urvashi", "Vidya", "Wasim", "Zoya", "Kiran", "Ritika"
]

INDIAN_LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Mehta", "Joshi", "Patel", "Reddy", "Nair",
    "Iyer", "Rao", "Singh", "Kumar", "Chopra", "Malhotra", "Bhatia", "Deshmukh",
    "Kulkarni", "Banerjee", "Chatterjee", "Sen", "Das", "Agarwal", "Saxena",
    "Mishra", "Pandey", "Kapoor", "Khanna", "Bansal", "Bose", "Menon"
]

INDIAN_CITIES = [
    "Bengaluru", "Mumbai", "Delhi NCR", "Hyderabad", "Pune", "Chennai",
    "Kolkata", "Ahmedabad", "Jaipur", "Chandigarh", "Indore", "Kochi"
]

FAILURE_SCENARIOS = [
    (
        "BAD_REQUEST_ERROR",
        "Payment failed at payment gateway",
        [PaymentMethod.UPI, PaymentMethod.CARD, PaymentMethod.NETBANKING, PaymentMethod.WALLET],
        0.20
    ),
    (
        "GATEWAY_ERROR",
        "Gateway timeout while communicating with acquiring bank",
        [PaymentMethod.UPI, PaymentMethod.NETBANKING, PaymentMethod.CARD],
        0.15
    ),
    (
        "BAD_REQUEST_ERROR",
        "Insufficient funds in customer account",
        [PaymentMethod.UPI, PaymentMethod.CARD, PaymentMethod.NETBANKING],
        0.18
    ),
    (
        "BAD_REQUEST_ERROR",
        "OTP entered was incorrect or expired",
        [PaymentMethod.CARD, PaymentMethod.NETBANKING, PaymentMethod.UPI],
        0.15
    ),
    (
        "BAD_REQUEST_ERROR",
        "Card transaction declined by issuing bank",
        [PaymentMethod.CARD],
        0.12
    ),
    (
        "CHECKOUT_ABANDONED",
        "Customer abandoned checkout session before payment attempt",
        [PaymentMethod.UPI, PaymentMethod.CARD, PaymentMethod.NETBANKING, PaymentMethod.WALLET],
        0.20
    ),
]

MICRO_CARTS = [
    ("Pack of 3 Ballpoint Pens", 2900),
    ("Micro USB Charging Cable 1m", 4900),
    ("Tempered Glass Screen Protector", 7900),
    ("Cotton Ankle Socks (Pack of 2)", 8900),
    ("Mobile Phone Ring Holder Stand", 9900),
]

RETAIL_CARTS = [
    ("Organic Green Tea 500g", 29900),
    ("Wireless Bluetooth Neckband", 69900),
    ("Running Shoes Size 9", 149900),
    ("Mixer Grinder 750W 3 Jars", 249900),
    ("Fast Charging Powerbank 20000mAh", 129900),
    ("Cotton King Bedsheet Set with Pillow Covers", 89900),
    ("Stainless Steel Water Bottle 1L", 49900),
    ("Men Slim Fit Casual Shirt", 119900),
    ("Mechanical Gaming Keyboard RGB", 349900),
    ("Noise Cancelling Wireless Earbuds Pro", 449900),
    ("Air Fryer 4.5L Digital Touch", 599900),
    ("Robotic Vacuum Cleaner with Mop", 1999900),
    ("4K Smart LED TV 43 inch", 2699900),
    ("Ergonomic Mesh Office Chair", 899900),
    ("Smartwatch with AMOLED Display", 399900),
]



def generate_dataset(seed: int = 42, wipe_db: bool = True) -> Tuple[List[Customer], List[FailedPayment]]:
    rng = random.Random(seed)

    if wipe_db:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        num_customers = 55
        customers: List[Customer] = []
        risk_flag_indices = set(rng.sample(range(num_customers), 7))

        propensity_pool = (
            [PropensityProfile.RELIABLE] * 14 +
            [PropensityProfile.DISTRACTED] * 17 +
            [PropensityProfile.HESITANT] * 11 +
            [PropensityProfile.BROKE] * 8 +
            [PropensityProfile.GHOST] * 5
        )
        rng.shuffle(propensity_pool)

        for j in range(num_customers):
            first_name = INDIAN_FIRST_NAMES[j % len(INDIAN_FIRST_NAMES)]
            last_name = rng.choice(INDIAN_LAST_NAMES)
            full_name = f"{first_name} {last_name}"
            clean_first = first_name.lower()
            clean_last = last_name.lower()

            cust_id = f"cust_{1000 + j}"
            phone = f"+9198{rng.randint(10000000, 99999999)}"
            email = f"{clean_first}.{clean_last}{j+1}@example.in"
            city = rng.choice(INDIAN_CITIES)

            is_risk = (j in risk_flag_indices)
            propensity = propensity_pool[j]

            if propensity in [PropensityProfile.RELIABLE, PropensityProfile.DISTRACTED]:
                tot = rng.randint(4, 25)
                fail = rng.randint(0, 2)
                avg_days = round(rng.uniform(0.1, 1.2), 1)
            elif propensity == PropensityProfile.HESITANT:
                tot = rng.randint(2, 10)
                fail = rng.randint(1, 4)
                avg_days = round(rng.uniform(1.0, 3.5), 1)
            elif propensity == PropensityProfile.BROKE:
                tot = rng.randint(1, 6)
                fail = rng.randint(2, 5)
                avg_days = round(rng.uniform(2.5, 6.0), 1)
            else:  # GHOST
                tot = rng.randint(0, 3)
                fail = rng.randint(1, 4)
                avg_days = round(rng.uniform(4.0, 10.0), 1)


            if is_risk:
                fail += rng.randint(3, 7)

            customer = Customer(
                id=cust_id,
                name=full_name,
                phone=phone,
                email=email,
                city=city,
                history_total_payments=tot,
                history_failed_payments=fail,
                history_avg_days_to_pay=avg_days,
                is_risk_flagged=is_risk,
                propensity_profile=propensity,
                created_at=datetime.now(timezone.utc) - timedelta(days=rng.randint(30, 365))
            )
            customers.append(customer)
            db.add(customer)

        db.flush()

        total_payments = 80
        customer_ids_for_payments = [c.id for c in customers]
        extra_customer_ids = [rng.choice(customers).id for _ in range(total_payments - num_customers)]
        payment_customer_assignment = customer_ids_for_payments + extra_customer_ids
        rng.shuffle(payment_customer_assignment)

        scenario_counts = [16, 12, 14, 12, 10, 16]
        all_scenarios = []
        for idx, count in enumerate(scenario_counts):
            all_scenarios.extend([FAILURE_SCENARIOS[idx]] * count)
        rng.shuffle(all_scenarios)

        micro_indices = set(rng.sample(range(total_payments), 10))
        train_indices = set(rng.sample(range(total_payments), 60))

        customer_map = {c.id: c for c in customers}
        failed_payments: List[FailedPayment] = []
        base_time = datetime.now(timezone.utc) - timedelta(hours=48)

        for i in range(total_payments):
            cust_id = payment_customer_assignment[i]
            cust_obj = customer_map[cust_id]
            scenario = all_scenarios[i]
            code, reason, allowed_methods, _ = scenario
            method = rng.choice(allowed_methods)

            if i in micro_indices:
                cart_title, amount_paise = rng.choice(MICRO_CARTS)
            else:
                cart_title, amount_paise = rng.choice(RETAIL_CARTS)

            offset_minutes = int((i / total_payments) * 44 * 60) + rng.randint(0, 120)
            failed_at = base_time + timedelta(minutes=offset_minutes)

            split = DatasetSplit.TRAIN if i in train_indices else DatasetSplit.HELD_OUT

            failed_payment = FailedPayment(
                id=f"pay_{2000 + i}",
                razorpay_order_id=f"order_{seed}_{100000 + i}",
                customer_id=cust_id,
                customer=cust_obj,
                amount_paise=amount_paise,
                currency="INR",
                method=method,
                failure_code=code,
                failure_reason=reason,
                failed_at=failed_at,
                cart_summary=cart_title,
                status=PaymentStatus.OPEN,
                dataset_split=split,
                created_at=failed_at
            )
            failed_payments.append(failed_payment)
            db.add(failed_payment)

        db.commit()
        return customers, failed_payments

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def print_summary_table(customers: List[Customer], failed_payments: List[FailedPayment], seed: int):
    sep = "=" * 78
    print("\n" + sep)
    print(f"  SYNTHETIC DATASET GENERATION SUMMARY (Seed: {seed})")
    print(sep)
    print(f" Total Customers Generated: {len(customers)}")
    print(f" Total Failed Payments:     {len(failed_payments)}")

    train_count = sum(1 for p in failed_payments if p.dataset_split == DatasetSplit.TRAIN)
    held_out_count = sum(1 for p in failed_payments if p.dataset_split == DatasetSplit.HELD_OUT)
    print("\n [Dataset Splits]")
    print(f"   * Train (60 target):    {train_count} ({train_count/len(failed_payments)*100:.1f}%)")
    print(f"   * Held-Out (20 target): {held_out_count} ({held_out_count/len(failed_payments)*100:.1f}%)")

    reason_counts: Dict[str, int] = {}
    for p in failed_payments:
        key = f"{p.failure_code} | {p.failure_reason[:36]}"
        reason_counts[key] = reason_counts.get(key, 0) + 1

    print("\n [Failure Categories Distribution]")
    print(f" {'Failure Code | Reason':<48} | {'Count':<6} | {'Share':<6}")
    print(" " + "-" * 66)
    for key, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
        share = count / len(failed_payments) * 100
        print(f" {key:<48} | {count:<6} | {share:>5.1f}%")

    method_counts: Dict[str, int] = {}
    for p in failed_payments:
        m = p.method.value if hasattr(p.method, "value") else str(p.method)
        method_counts[m] = method_counts.get(m, 0) + 1

    print("\n [Payment Method Breakdown]")
    for m, c in sorted(method_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"   * {m.upper():<12}: {c:<3} ({c/len(failed_payments)*100:.1f}%)")

    amounts = [p.amount_rupees for p in failed_payments]
    under_100 = sum(1 for a in amounts if a < 100.0)
    print("\n [Amount Statistics]")
    print(f"   * Min Amount:         Rs. {min(amounts):.2f}")
    print(f"   * Max Amount:         Rs. {max(amounts):.2f}")
    print(f"   * Average Amount:     Rs. {sum(amounts)/len(amounts):.2f}")
    print(f"   * Micro (< Rs. 100):  {under_100} transactions (exercises cost-of-contact gate)")


    risk_customers = sum(1 for c in customers if c.is_risk_flagged)
    print("\n [Risk Flagging & Guardrails]")
    print(f"   * Risk-Flagged Customers: {risk_customers} (exercises do-not-contact gate)")


    print("\n [Simulator Ground Truth (Invisible to Agent)]")
    prop_counts: Dict[str, int] = {}
    for c in customers:
        pr = c.propensity_profile.value if hasattr(c.propensity_profile, "value") else str(c.propensity_profile)
        prop_counts[pr] = prop_counts.get(pr, 0) + 1
    for pr, c in sorted(prop_counts.items()):
        print(f"   * {pr:<12}: {c} customers")


    print(sep + "\n")


def main():
    parser = argparse.ArgumentParser(description="Synthetic Dataset Generator")
    parser.add_argument("--seed", type=int, default=settings.RANDOM_SEED, help="Random seed for reproducibility")
    parser.add_argument("--no-wipe", action="store_true", help="Do not wipe existing DB tables")
    args = parser.parse_args()

    print(f"\nGenerating synthetic dataset with seed={args.seed}...")
    customers, failed_payments = generate_dataset(seed=args.seed, wipe_db=not args.no_wipe)
    print_summary_table(customers, failed_payments, seed=args.seed)


if __name__ == "__main__":
    main()
