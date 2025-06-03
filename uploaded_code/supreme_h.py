import os
import sqlite3
import pandas as pd

def calculate_bank_fees():
    print('[FUNCTION] calculate_bank_fees')

    ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
    db_path = os.path.join(ROOT_DIR, "data", "Supreme.db")

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return None

    conn = sqlite3.connect(db_path)
    bank_master = pd.read_sql_query("SELECT * FROM bank_master_upload", conn)
    conn.close()

    bank_master['amount'] = pd.to_numeric(bank_master['amount'], errors='coerce')

    keywords = ['Fee-', 'EFTNP-']
    pattern = "|".join(keywords)

    bank_fee = bank_master[
        bank_master['description'].str.contains(pattern, na=False, case=False) &
        (bank_master['amount'] < 0)
    ].copy()

    bank_fee = bank_fee[['txn_date', 'effective', 'description', 'amount']]

    conn = sqlite3.connect(db_path)
    bank_fee.to_sql("bank_fee", conn, if_exists='replace', index=False)
    conn.close()

    print("✅ Saved bank_fee to DB")
    return bank_fee

import os
import sqlite3
import pandas as pd
import numpy as np

def calculate_bank_grinrod():
    print('[FUNCTION] calculate_bank_grinrod')

    ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
    db_path = os.path.join(ROOT_DIR, "data", "Supreme.db")

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return pd.DataFrame()

    # ✅ Utility to check if table exists
    def table_exists(conn, table_name):
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        return pd.read_sql(query, conn, params=(table_name,)).shape[0] > 0

    conn = sqlite3.connect(db_path)

    # ✅ Step 1: Load or fallback for tables
    bank_master = pd.read_sql_query("SELECT * FROM bank_master_upload", conn) if table_exists(conn, "bank_master_upload") else pd.DataFrame()
    grinrod = pd.read_sql_query("SELECT * FROM grinrod_upload", conn) if table_exists(conn, "grinrod_upload") else pd.DataFrame(columns=['policy_number', 'monthly_instalment'])
    bord = pd.read_sql_query("SELECT * FROM bordereaux_upload", conn) if table_exists(conn, "bordereaux_upload") else pd.DataFrame(columns=['policy_number', 'product_name'])

    conn.close()

    if bank_master.empty:
        print("❌ bank_master_upload table is missing or empty.")
        return pd.DataFrame()

    # ✅ Step 2: Filter EFT-EFT DEBIT rows
    bank_master['amount'] = pd.to_numeric(bank_master['amount'], errors='coerce')
    pattern = "EFT-EFT DEBIT"

    bank_grinrod = bank_master[
        bank_master['description'].str.contains(pattern, na=False, case=False) &
        (bank_master['amount'] > 0)
    ].copy()

    if bank_grinrod.empty:
        print("❌ No matching EFT-EFT DEBIT rows found in bank_master.")
        return pd.DataFrame()

    with sqlite3.connect(db_path) as conn:
        bank_grinrod.to_sql("bank_grinrod_master", conn, if_exists="replace", index=False)

    # ✅ Step 3: Prepare grinrod data
    if grinrod.empty:
        print("⚠️ grinrod_upload table missing or empty. Skipping transformation.")
        return pd.DataFrame()

    bank_grinrod_2 = grinrod.copy()
    latest_txn_date = bank_grinrod['txn_date'].iloc[-1]
    latest_effective = bank_grinrod['effective'].iloc[-1]

    bank_grinrod_2['txn_date'] = latest_txn_date
    bank_grinrod_2['effective'] = latest_effective
    bank_grinrod_2['description'] = bank_grinrod_2['policy_number']

    bank_grinrod_2 = bank_grinrod_2[[
        'txn_date', 'effective', 'description', 'monthly_instalment', 'policy_number'
    ]].rename(columns={
        'monthly_instalment': 'amount',
        'policy_number': 'policy'
    })

    # ✅ Step 4: Merge with bordereaux
    if bord.empty:
        print("⚠️ bordereaux_upload table missing or empty. Skipping merge.")
        return bank_grinrod_2

    bord['policy'] = bord['policy_number']
    bord = bord.drop_duplicates(subset=['policy_number'])

    merged = pd.merge(
        bank_grinrod_2,
        bord[['policy', 'product_name']],
        on='policy',
        how='outer',
        indicator=True,
        suffixes=('_grin', '_bord')
    )

    merged = merged[merged['_merge'] == 'both'].copy()
    merged['amount'] = pd.to_numeric(merged['amount'], errors='coerce').fillna(0)

    # ✅ Step 5: Underwriters Premium
    def calculate_underwriters_premium(amount):
        if amount % 55 == 0 or abs(amount - 220) <= 0.9:
            return (amount / 220) * 56
        return np.nan

    merged['underwriters_premium'] = round(
        merged['amount'].apply(calculate_underwriters_premium), 2
    )

    merged['indicator'] = ''
    mask = merged['underwriters_premium'].isna()
    merged.loc[mask, 'underwriters_premium'] = (merged.loc[mask, 'amount'] / 2).round(2)
    merged.loc[mask, 'indicator'] = 'divide by 2'

    # ✅ Step 6: Save result
    conn = sqlite3.connect(db_path)
    merged.to_sql("bank_grinrod", conn, if_exists='replace', index=False)
    conn.close()

    print(f"✅ Saved bank_grinrod to DB — {len(merged)} rows")
    return merged



def calculate_bank_nupay():
    print('[FUNCTION] calculate_bank_nupay')

    ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
    db_path = os.path.join(ROOT_DIR, "data", "Supreme.db")

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return pd.DataFrame()

    def table_exists(conn, table_name):
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        return pd.read_sql(query, conn, params=(table_name,)).shape[0] > 0

    conn = sqlite3.connect(db_path)

    # Load tables or fallback
    bank_master = pd.read_sql("SELECT * FROM bank_master_upload", conn) if table_exists(conn, "bank_master_upload") else pd.DataFrame()
    nupay = pd.read_sql("SELECT * FROM nupay_upload", conn) if table_exists(conn, "nupay_upload") else pd.DataFrame(columns=['user_reference', 'debtor_id', 'mandate_id'])
    bord = pd.read_sql("SELECT * FROM bordereaux_upload", conn) if table_exists(conn, "bordereaux_upload") else pd.DataFrame(columns=['payer_id_no', 'nupay_mandate_id', 'member_type', 'id_number', 'policy_number'])

    conn.close()

    if bank_master.empty:
        print("❌ bank_master_upload table is missing or empty.")
        return pd.DataFrame()

    # Convert amount to numeric
    bank_master['amount'] = pd.to_numeric(bank_master['amount'], errors='coerce')

    # ✅ Step 1: Filter SF Funeral payments
    keyword = "SF Funeral"
    bank_nupay = bank_master[
        bank_master['description'].str.contains(keyword, na=False, case=False) &
        (bank_master['amount'] > 0)
    ].copy()

    if bank_nupay.empty:
        print("❌ No matching SF Funeral rows found.")
        return pd.DataFrame()

    # ✅ Step 2: Save raw filter to master table
    with sqlite3.connect(db_path) as conn:
        bank_nupay.to_sql("bank_nupay_master", conn, if_exists="replace", index=False)

    # ✅ Step 3: Merge with nupay
    nupay = nupay.rename(columns={'user_reference': 'description_1'})
    bank_nupay['description_1'] = bank_nupay['description']

    bank_nupay_merged = pd.merge(
        bank_nupay,
        nupay[['description_1', 'debtor_id', 'mandate_id']],
        on='description_1',
        how='outer',
        indicator=True
    )
    bank_nupay_merged = bank_nupay_merged[bank_nupay_merged['_merge'] == 'both'].drop(columns=['_merge'])

    # ✅ Step 4: Map policy_number using bordereaux
    bord['debtor_id'] = bord['payer_id_no']
    bord['mandate_id'] = bord['nupay_mandate_id']
    bord_p = bord[bord['member_type'] == 'Policy Holder'].copy()
    bord_p.loc[bord_p['debtor_id'].isna(), 'debtor_id'] = bord_p['id_number']

    # Pass 1: debtor_id == id_number
    bord_p_1 = bord_p[bord_p['debtor_id'] == bord_p['id_number']]
    mapping_1 = bord_p_1.groupby('debtor_id')['policy_number'].first().to_dict()
    bank_nupay_merged['policy_number'] = bank_nupay_merged['debtor_id'].map(mapping_1)

    # Pass 2: map via mandate_id
    unmatched_mask = bank_nupay_merged['policy_number'].isna()
    mapping_2 = bord_p.groupby('mandate_id')['policy_number'].first().to_dict()
    bank_nupay_merged.loc[unmatched_mask, 'policy_number'] = bank_nupay_merged.loc[unmatched_mask, 'mandate_id'].map(mapping_2)

    # Pass 3: map remaining via unmatched debtor_id
    unmatched_mask = bank_nupay_merged['policy_number'].isna()
    bord_p_2 = bord_p[bord_p['debtor_id'] != bord_p['id_number']]
    mapping_3 = bord_p_2.groupby('debtor_id')['policy_number'].first().to_dict()
    bank_nupay_merged.loc[unmatched_mask, 'policy_number'] = bank_nupay_merged.loc[unmatched_mask, 'debtor_id'].map(mapping_3)

    still_unmatched = bank_nupay_merged['policy_number'].isna().sum()
    print(f"❗ Still unmatched policy numbers: {still_unmatched}")

    # ✅ Step 5: Save final result
    with sqlite3.connect(db_path) as conn:
        bank_nupay_merged.to_sql("bank_nupay", conn, if_exists="replace", index=False)

    print(f"✅ Saved bank_nupay to DB — {len(bank_nupay_merged)} rows")
    return bank_nupay_merged


def finalize_bank_nupay():
    print('[FUNCTION] finalize_bank_nupay')

    ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
    db_path = os.path.join(ROOT_DIR, "data", "Supreme.db")

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return pd.DataFrame()

    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM bank_nupay", conn)
    bord = pd.read_sql("SELECT * FROM bordereaux_upload", conn)
    conn.close()

    # Add lowercase key column for merging
    df['key'] = df['policy_number'].astype(str).str.strip().str.lower()
    bord['key'] = bord['policy_number'].astype(str).str.strip().str.lower()
    bord_unique = bord.drop_duplicates(subset=['key'])

    # Merge to get product_name
    df = pd.merge(df, bord_unique[['key', 'product_name']], on='key', how='left')
    df.drop(columns=['key'], inplace=True)

    # Calculate Underwriters Premium
    def calculate_uw_premium(amount):
        if pd.isna(amount):
            return np.nan
        if amount % 55 == 0 or abs(amount - 220) <= 0.9:
            return (amount / 220) * 56
        return np.nan

    df['underwriters_premium'] = round(df['amount'].astype(float).apply(calculate_uw_premium), 2)

    df['indicator'] = ''
    mask = df['underwriters_premium'].isna()
    df.loc[mask, 'underwriters_premium'] = (df.loc[mask, 'amount'] / 2).round(2)
    df.loc[mask, 'indicator'] = 'divide by 2'

    # Save finalized table
    with sqlite3.connect(db_path) as conn:
        df.to_sql("bank_nupay", conn, if_exists="replace", index=False)

    print(f"✅ Final NuPay saved to 'bank_nupay' — {len(df)} rows")
    return df

import os
import sqlite3
import pandas as pd
import numpy as np

def calculate_bank_refund():
    print('[FUNCTION] calculate_bank_refund')

    ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
    db_path = os.path.join(ROOT_DIR, "data", "Supreme.db")

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return pd.DataFrame()

    print('Import data')
    conn = sqlite3.connect(db_path)
    bank_master = pd.read_sql("SELECT * FROM bank_master_upload", conn)
    refunds = pd.read_sql("SELECT * FROM refunds_upload", conn)
    nupay = pd.read_sql("SELECT * FROM nupay_upload", conn)
    nupay_old = pd.read_sql("SELECT * FROM nupay_database", conn)
    bord = pd.read_sql("SELECT * FROM bordereaux_upload", conn)
    bank_nupay_2_merge = pd.read_sql("SELECT * FROM bank_nupay", conn)
    conn.close()

    print('Step 1')
    bank_master['amount'] = pd.to_numeric(bank_master['amount'], errors='coerce')
    keywords = ['Rev SF', 'Supreme Refunds']
    pattern = "|".join(keywords)

    bank_refund = bank_master[
        bank_master['description'].str.contains(pattern, na=False, case=False) &
        (bank_master['amount'] < 0)
    ].copy()

    with sqlite3.connect(db_path) as conn:
        bank_refund.to_sql("bank_refund_master", conn, if_exists="replace", index=False)

    print('Step 2')
    bank_refund_2 = refunds.copy()
    supreme_refunds = bank_master[
        (bank_master['description'].str.contains('Supreme Refunds', na=False)) &
        (bank_master['amount'] < 0)
    ]
    if not supreme_refunds.empty:
        txn_date = supreme_refunds.iloc[0]['txn_date']
        effective = supreme_refunds.iloc[0]['effective']
        bank_refund_2['txn_date'] = txn_date
        bank_refund_2['effective'] = effective
    else:
        raise ValueError("❌ No 'Supreme Refunds' row found in bank_master.")

    bank_refund_2['description'] = bank_refund_2['policy_number']
    bank_refund_2 = bank_refund_2[bank_refund_2['description'].notna()]
    bank_refund_2 = bank_refund_2[['txn_date', 'effective', 'description', 'amount', 'policy_number']]
    bank_refund_2['amount'] = bank_refund_2['amount'].astype(float) * -1

    print('Step 3')
    nupay_old = pd.concat([nupay_old, nupay[['mandate_id', 'user_reference', 'debtor_id']]], ignore_index=True)
    nupay_old['user_reference'] = nupay_old['user_reference'].str.replace(' ', '')
    nupay_old['debtor_id'] = nupay_old['debtor_id'].astype(str).str.zfill(13)
    nupay_old.drop_duplicates(['user_reference'], inplace=True)

    print('Step 4')
    bank_refund['user_reference'] = bank_refund['description'].str.replace('Rev ', '', regex=False).str.replace(' ', '')

    print('Step 5')
    bank_refund_2_merge = pd.merge(
        bank_refund,
        nupay_old,
        on='user_reference',
        how='outer',
        indicator=True
    )
    bank_refund_2_merge = bank_refund_2_merge[bank_refund_2_merge['_merge'] != 'right_only'].drop(columns=['_merge'])

    print('Step 6')
    def clean_policy(val):
        return str(val).replace(' ', '').strip().lower()

    bank_nupay_2_merge['user_reference'] = bank_nupay_2_merge['description'].copy()
    bank_nupay_2_merge['key'] = bank_nupay_2_merge['user_reference'].apply(clean_policy)
    bank_refund_2_merge['key'] = bank_refund_2_merge['user_reference'].apply(clean_policy)

    bank_nupay_2_merge_1 = bank_nupay_2_merge[['key', 'policy_number']]
    bank_refund_2_merge = pd.merge(
        bank_refund_2_merge,
        bank_nupay_2_merge_1,
        on='key',
        how='outer',
        indicator=True
    )
    bank_refund_2_merge = bank_refund_2_merge[bank_refund_2_merge['_merge'] != 'right_only'].drop(columns=['_merge'])
    print('bank_refund_2_merge')
    print(bank_refund_2_merge.columns)

    print('Step 7')
    ### Die rename van die stap moet nie eintlik hier wees nie moet dit reg maak
    bank_refund_2_merge = bank_refund_2_merge.rename(columns={
    'policy_number_y': 'policy_number'
    })
    bank_refund_2_merge.loc[(bank_refund_2_merge['policy_number_x'].notna()) &
                            (bank_refund_2_merge['policy_number'].isna()), 'policy_number'] = bank_refund_2_merge['policy_number_x']
    ##########################################################################
    unmatched_mask = bank_refund_2_merge['policy_number'].isna()
    mapping_debtor = bank_nupay_2_merge.groupby('debtor_id')['policy_number'].first().to_dict()
    bank_refund_2_merge.loc[unmatched_mask, 'policy_number'] = (
        bank_refund_2_merge.loc[unmatched_mask, 'debtor_id'].map(mapping_debtor)
    )

    print('Step 8')
    bord['debtor_id'] = bord['payer_id_no'].copy()
    bord['mandate_id'] = bord['nupay_mandate_id'].copy()
    unmatched_mask = bank_refund_2_merge['policy_number'].isna()
    policy_map_bord_debtor = bord.groupby('debtor_id')['policy_number'].first().to_dict()
    bank_refund_2_merge.loc[unmatched_mask, 'policy_number'] = (
        bank_refund_2_merge.loc[unmatched_mask, 'debtor_id'].map(policy_map_bord_debtor)
    )

    print('Step 9')
    bord_p = bord[bord['policy_number'].notna()]
    unmatched_mask = bank_refund_2_merge['policy_number'].isna()
    unmatched_debtors = bank_refund_2_merge.loc[unmatched_mask, 'mandate_id']
    policy_mapping_2 = bord_p.groupby('mandate_id')['policy_number'].first().to_dict()
    bank_refund_2_merge.loc[unmatched_mask, 'policy_number'] = unmatched_debtors.map(policy_mapping_2)

    print('Step 10')
    bank_refund_3_merge = pd.concat([bank_refund_2_merge, bank_refund_2], ignore_index=True)
    bank_refund_3_merge['key'] = bank_refund_3_merge['policy_number'].apply(clean_policy)
    bord['key'] = bord['policy_number'].apply(clean_policy)

    bord_drop = bord.drop_duplicates(subset='key')
    bank_refund_3_merge = pd.merge(
        bank_refund_3_merge,
        bord_drop[['key', 'product_name']],
        on='key',
        how='left'
    )

    bank_refund_3_merge = bank_refund_3_merge[~(bank_refund_3_merge['description'].str.contains('Supreme Refunds'))]

    print('Step 11')
    def calculate_underwriters_premium(amount):
        if pd.isna(amount): return np.nan
        if amount % 55 == 0 or abs(amount - 220) <= 0.9:
            return (amount / 220) * 56
        return np.nan

    bank_refund_3_merge['underwriters_premium'] = round(
        bank_refund_3_merge['amount'].astype(float).apply(calculate_underwriters_premium), 2
    )
    bank_refund_3_merge['indicator'] = ''
    mask = bank_refund_3_merge['underwriters_premium'].isna()
    bank_refund_3_merge.loc[mask, 'underwriters_premium'] = (bank_refund_3_merge.loc[mask, 'amount'] / 2).round(2)
    bank_refund_3_merge.loc[mask, 'indicator'] = 'divide by 2'

    unmatched_final = bank_refund_3_merge['policy_number'].isna().sum()
    print(f"✅ Saved bank_refund to DB — {len(bank_refund_3_merge)} rows")
    print(f"❗ Still unmatched policy numbers: {unmatched_final}")

    with sqlite3.connect(db_path) as conn:
        bank_refund_3_merge.to_sql("bank_refund", conn, if_exists='replace', index=False)

    return bank_refund_3_merge, unmatched_final


import os
import sqlite3
import pandas as pd
import numpy as np

def calculate_bank_cash():
    print('[FUNCTION] calculate_bank_cash')

    ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
    db_path = os.path.join(ROOT_DIR, "data", "Supreme.db")

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return pd.DataFrame()

    print('Importing data...')
    conn = sqlite3.connect(db_path)
    bank_master = pd.read_sql("SELECT * FROM bank_master_upload", conn)
    bord = pd.read_sql("SELECT * FROM bordereaux_upload", conn)
    conn.close()

    bank_master['amount'] = pd.to_numeric(bank_master['amount'], errors='coerce')

    # Step 1: Filter for cash deposits
    print('Step 1')
    keywords = ['EFT-', 'RTC-', 'Dep-Cash']
    pattern = "|".join(keywords)

    bank_cash = bank_master[
        (bank_master['description'].str.contains(pattern, na=False, case=False)) &
        (bank_master['amount'] > 0)
    ].copy()

    # Exclude EFT-EFT DEBIT rows
    bank_cash = bank_cash[~(
        (bank_cash['description'].str.contains('EFT-EFT DEBIT', na=False)) &
        (bank_cash['amount'] > 0)
    )]

    # Step 2: Extract key from description
    print('Step 2')
    bank_cash['key'] = bank_cash['description']
    for prefix in ['Dep-Cash-', 'EFT-', 'RTC-']:
        bank_cash['key'] = bank_cash['key'].str.replace(prefix, '', regex=False)

    def extract_last_word(s):
        return s.split()[-1] if len(s.split()) > 1 else s

    bank_cash['key'] = bank_cash['key'].apply(extract_last_word)

    # Step 3: Initialize missing columns
    print('Step 3')
    bank_cash['policy_number'] = np.nan
    bank_cash['product_name'] = np.nan
    bank_cash['policy_number'] = bank_cash['policy_number'].astype('object')
    bank_cash['product_name'] = bank_cash['product_name'].astype('object')

    # Step 4: Match by policy_number directly
    print('Step 4')
    unmatched = bank_cash['policy_number'].isna()
    bank_cash.loc[unmatched, 'policy_number'] = bank_cash.loc[unmatched, 'key'].map(
        bord.groupby('policy_number')['policy_number'].first().to_dict()
    )
    bank_cash.loc[unmatched, 'product_name'] = bank_cash.loc[unmatched, 'key'].map(
        bord.groupby('policy_number')['product_name'].first().to_dict()
    )

    # Step 5: Match by debtor_id
    print('Step 5')
    bord['debtor_id'] = bord['payer_id_no']
    unmatched = bank_cash['policy_number'].isna()
    bank_cash.loc[unmatched, 'policy_number'] = bank_cash.loc[unmatched, 'key'].map(
        bord.groupby('debtor_id')['policy_number'].first().to_dict()
    )
    bank_cash.loc[unmatched, 'product_name'] = bank_cash.loc[unmatched, 'key'].map(
        bord.groupby('debtor_id')['product_name'].first().to_dict()
    )

    # Step 6: Match by id_number
    print('Step 6')
    unmatched = bank_cash['policy_number'].isna()
    bank_cash.loc[unmatched, 'policy_number'] = bank_cash.loc[unmatched, 'key'].map(
        bord.groupby('id_number')['policy_number'].first().to_dict()
    )
    bank_cash.loc[unmatched, 'product_name'] = bank_cash.loc[unmatched, 'key'].map(
        bord.groupby('id_number')['product_name'].first().to_dict()
    )

    # Step 7: Calculate underwriters premium
    print('Step 7')
    def calc_uw(amount):
        if pd.isna(amount): return np.nan
        if amount % 55 == 0 or abs(amount - 220) <= 0.9:
            return (amount / 220) * 56
        return np.nan

    bank_cash['underwriters_premium'] = round(bank_cash['amount'].astype(float).apply(calc_uw), 2)
    bank_cash['indicator'] = ''
    mask = bank_cash['underwriters_premium'].isna()
    bank_cash.loc[mask, 'underwriters_premium'] = (bank_cash.loc[mask, 'amount'] / 2).round(2)
    bank_cash.loc[mask, 'indicator'] = 'divide by 2'

    # Step 8: Save
    print('Step 8')
    unmatched_count = bank_cash['policy_number'].isna().sum()
    print(f"❗ Still unmatched policy numbers: {unmatched_count}")

    with sqlite3.connect(db_path) as conn:
        bank_cash.columns = bank_cash.columns.str.strip().str.lower().str.replace(" ", "_")
        bank_cash.to_sql("bank_cash_temp", conn, if_exists="replace", index=False)

    return bank_cash, unmatched_count


import os
import sqlite3
import pandas as pd

def finalize_bank_cash():
    print('[FUNCTION] finalize_bank_cash')

    ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
    db_path = os.path.join(ROOT_DIR, "data", "Supreme.db")

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return

    try:
        # Load from temp
        conn = sqlite3.connect(db_path)
        df = pd.read_sql("SELECT * FROM bank_cash_temp", conn)
        conn.close()

        print(f"✅ Loaded {len(df)} rows from bank_cash_temp")

        # Save as final
        conn = sqlite3.connect(db_path)
        df.to_sql("bank_cash", conn, if_exists='replace', index=False)
        conn.close()

        print(f"✅ Final bank_cash saved with {len(df)} rows")

    except Exception as e:
        print(f"❌ Error during finalization: {e}")


