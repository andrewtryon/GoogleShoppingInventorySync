import ftplib
import pandas as pd
import pyodbc
import numpy as np
import csv
    
if __name__ == '__main__':

    logf = open("GoogleActionFeedError.log", "w")
    try:
        #Connection String
        conn_str = (
            r'DSN=SOTAMAS90;'
            r'UID=***********;'
            r'PWD=****************;'
            r'Directory=\\sage100\sage 100 Advanced\2018\MAS90;'
            r'Prefix=\MAS90\SY\, \\sage100\Sage 100 Advanced\2018\MAS90\==\;'
            r'ViewDLL=\\sage100\Sage 100 Advanced\2018\MAS90\HOME;'
            r'Company=FOT;'
            r'LogFile=\PVXODBC.LOG;'
            r'CacheSize=4;'
            r'DirtyReads=1;'
            r'BurstMode=1;'
            r'StripTrailingSpaces=1;'
            r'SERVER=NotTheServer;'
            )

        #Establish sage connection
        print('Connecting to Sage')
        cnxn = pyodbc.connect(conn_str, autocommit=True)    
        
        #SQL Sage data into dataframe
        sql = """
            SELECT 
                CI_Item.UDF_OSC_ID as 'id',
                CI_Item.ProductLine,
                CI_Item.UDF_MAP_PRICE,            
                CI_Item.StandardUnitCost,
                CI_Item.StandardUnitPrice,
                CI_Item.SuggestedRetailPrice,
                CI_Item.ShipWeight,
                IM_ItemWarehouse.QuantityOnHand,
                IM_ItemWarehouse.QuantityOnSalesOrder,
                IM_ItemWarehouse.QuantityOnBackOrder,
                CI_Item.ProductType 
            FROM 
                CI_Item CI_Item, 
                IM_ItemWarehouse IM_ItemWarehouse
            WHERE 
                CI_Item.ItemCode = IM_ItemWarehouse.ItemCode AND
                (CI_Item.InactiveItem is Null or CI_Item.InactiveItem = 'N') AND
                IM_ItemWarehouse.WarehouseCode = '000'
        """
        #Execute SQL
        SageDF = pd.read_sql(sql,cnxn)

        #Cleanup for export ....and defaults
        SageDF = SageDF.dropna(subset=['id'])
        SageDF['id'] = SageDF['id'].astype(str)
        SageDF['id'] = SageDF['id'] + '0'
        SageDF['ShipWeight'] = pd.to_numeric(SageDF['ShipWeight'],errors='coerce')
        SageDF['sales_margin'] = (SageDF['StandardUnitPrice'] - SageDF['StandardUnitCost']) / SageDF['StandardUnitPrice']
        SageDF = SageDF.loc[SageDF['id'] != '0.00']
        SageDF['sell_on_google_quantity'] = SageDF['QuantityOnHand'] - SageDF['QuantityOnSalesOrder'] - SageDF['QuantityOnBackOrder']
        SageDF.loc[SageDF['sell_on_google_quantity'] < 0, 'sell_on_google_quantity'] = 0

        #Defaults .... things not on Google Shopping Actions
        SageDF['excluded_destination'] = 'Shopping Actions'
        SageDF['included_destination'] = 'Display Ads,Shopping Ads,Surfaces across Google'

        #actual BI logic here .... i.e. Turn on Google Shopping ACtions for items that have a blank ('') in the 'excluded_destination'
        SageDF.loc[(SageDF['sell_on_google_quantity'] > 0) & (SageDF['UDF_MAP_PRICE'] > 0) & (SageDF['ProductLine'] == 'NFLU'), 'excluded_destination'] = '' #All Fluke MAP items
        SageDF.loc[(SageDF['sell_on_google_quantity'] > 0) & (SageDF['StandardUnitPrice'] > 200) & (SageDF['sales_margin'] > .2) & (SageDF['ProductLine'].str.startswith('N')), 'excluded_destination'] = '' #Gross Margin > 20, Price > 250, New product line
        SageDF.loc[(SageDF['sell_on_google_quantity'] > 0) & (SageDF['StandardUnitPrice'] > 500) & (SageDF['sales_margin'] > .18) & (SageDF['ProductLine'].str.startswith('N')), 'excluded_destination'] = '' #Gross Margin > 18, Price > 500, New product line

        #
        SageDF.loc[(SageDF['ShipWeight'] > 30), 'excluded_destination'] = 'Shopping Actions' #All Fluke MAP items

        #Wrap up BI Logic for feed
        SageDF.loc[(SageDF['excluded_destination'] == ''), 'included_destination'] = 'Display Ads,Shopping Ads,Shopping Actions,Surfaces across Google'
        SageDF.loc[(SageDF['excluded_destination'] != ''), 'sell_on_google_quantity'] = 0
        #SageDF = SageDF.loc[(SageDF['sell_on_google_quantity'] != 0)]
        
        #SageDF.to_csv('./SellingOnGoogle/sell_on_google_quantity.tsv', sep='\t', index = False, columns = ['id','sell_on_google_quantity','excluded_destination','included_destination'], quoting=csv.QUOTE_ALL)
    
        print(SageDF)
        SageDF.to_csv('./SellingOnGoogle/sell_on_google_quantity.tsv', sep='\t', index = False, columns = ['id','sell_on_google_quantity','excluded_destination','included_destination'])
        #FTP
        session = ftplib.FTP('uploads.google.com','**************','**************')
        file = open('./SellingOnGoogle/sell_on_google_quantity.tsv','rb')
        session.storbinary('STOR sell_on_google_quantity.tsv', file)
        file.close()
        session.quit()
    except Exception as e:     # most generic exception you can catch
        print(e)
        logf.write("Error :( {0}\n".format(str(e)))
        # optional: delete local version of failed download
    finally:
        # optional clean up code
        pass        
    