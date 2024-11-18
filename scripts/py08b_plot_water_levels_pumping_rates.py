import os
import glob
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Qt5Agg')
import flopy.utils.binaryfile as bf

"Author: RWeatherl, modified by MPedrazas"
cwd = os.getcwd()
wdir = os.path.dirname(cwd)

### --- 1. Import and structure all data --- ###
def import_WL_data():

    data_files = glob.glob(os.path.join(os.path.dirname(cwd), 'data', 'water_levels', '*.xlsx'))

    all_data = {}
    for file in data_files:
       # print(file.split("\\")[-1].split('.')[0]) ## extract filename directory and use as dict key
        k = file.split("\\")[-1].split('.')[0]
        all_data[k] = pd.read_excel(file, sheet_name = None, engine='openpyxl') #, index_col = 0, parse_dates=True)

    strings = [data_files[i].split("\\")[-1].split('.')[0] for i, e in enumerate(data_files)] ## isolate file names without .xlsx extension
    dict1, dict2, dict3 = all_data[strings[0]].copy(), all_data[strings[1]].copy(), all_data[strings[2]].copy() ## separate data from nested dict into simple dict. create copy to avoid edits to original data.

    ## manipulations on individual dictionaries. Create consistent Date, ID, and water level columns to later combine all dicts into 1 df
    for k in dict1:
        dict1[k] = dict1[k].iloc[9:]
        dict1[k].columns = dict1[k].iloc[0]
        dict1[k].drop(dict1[k].index[0], inplace=True)
        dict1[k].set_index('Date and Time', inplace=True)
        dict1[k].index = pd.to_datetime(dict1[k].index)
        dict1[k].index.name = 'Date'
        dict1[k].insert(0, 'ID', k)
        dict1[k].rename(columns = {'Elevation of the water level in the well (m)': 'Water Level (m)'}, inplace = True)
        # print(dict1[k].columns)  ##check correct column name assignment

    for k in dict2:
        dict2[k].set_index('Date/Time', inplace=True)
        dict2[k].index = pd.to_datetime(dict2[k].index)
        dict2[k].index.name = 'Date'
        dict2[k].insert(0, 'ID', k)
        dict2[k].rename(columns={'Elevation (m)': 'Water Level (m)'}, inplace=True)

    for k in dict3:
        dict3[k].set_index('HYD_DATE_TIME_PST', inplace=True)
        dict3[k].index = pd.to_datetime(dict3[k].index)
        dict3[k].index.name = 'Date'
        dict3[k].insert(0, 'ID', k)
        dict3[k].rename(columns={'HYD_HEAD_METERS_NAVD88': 'Water Level (m)'}, inplace=True)

    ## combine all 3 separate dicts into one master dict
    masterdict = {**dict1, **dict2, **dict3}

    ## concatenate all into dataframe
    df = pd.concat([v for k, v in masterdict.items()])[['ID', 'Water Level (m)']]
    df['Water Level (m)'] = pd.to_numeric(df['Water Level (m)'])
    df_sp = df.reset_index()
    ## resample
    df_sp.set_index(['ID', 'Date'], inplace = True)
    ## resample to daily
    df_sp = df_sp.groupby([pd.Grouper(level = 'ID'),
                       pd.Grouper(freq = 'D', level=-1)]).mean()
    # resample to monthly
    df_sp_m = df_sp.groupby([pd.Grouper(level = 'ID'),
                       pd.Grouper(freq = 'MS', level=-1)]).mean()

    return df, df_sp, df_sp_m

def read_head(ifile_hds, df, all_lays=False):
    """
       This fn will take in a data frame to loop through Rows, Columns, Times, Layers and extract Heads
       Input:  dataframe
               all_lays = False if you only want the 1st Layer OR
               all_lays = True if you want ALL the model layers
       """
    # import model heads
    hds_obj = bf.HeadFile(ifile_hds, verbose=False)
    times = hds_obj.get_times()
    data = hds_obj.get_alldata(mflay=None)
    ntimes, nlay, nr, nc = data.shape

    if all_lays:
        nlays = range(nlay)
    else:
        nlays = [0]
    vals = []
    for idx, row, col in zip(range(len(df)), df.Row, df.Col):
        for t_idx, t in enumerate(times):
            for lay in nlays:
                vals.append([data[t_idx][lay][row][col], t, lay + 1, row, col, df.NAME.iloc[idx]])  # 237 nodes * 84 times = 19908 vals for L1
    df_return = pd.DataFrame(vals, columns=['Head', 'Time', 'Layer', 'Row', 'Column', 'NAME'])
    df_return.drop_duplicates(inplace=True)
    #df_return.to_csv(os.path.join('output', 'water_level_data', f'{sce}', "simulated_heads_flopy.csv"), index=False)
    return df_return

def read_model_grid():
    """
    input : grid_with_centroids.shp <-- shapefile of model grid
    :return: grid <-- geopandas dataframe for model grid
    """
    print('reading grid file')
    grid = gpd.read_file(os.path.join(os.path.dirname(cwd), 'gis', 'shp', 'grid_with_centroids.shp'))
    print('finished reading grid file')
    return grid

def get_wells_ij(df, coordscsv):
    print("Getting row and column info for each well")
    coords_database = pd.read_csv(coordscsv, delimiter = "|")
    well_lst = list(df['ID'].unique())
    wells = coords_database.loc[coords_database.NAME.isin(well_lst)]

    ## create GDF from wells dataframe and merge with grid
    grid = read_model_grid()
    mycrs = grid.crs
    wells_gdf = gpd.GeoDataFrame(wells,
                                 geometry=gpd.points_from_xy(wells['XCOORDS'], wells['YCOORDS']),
                                 crs=mycrs)

    gridwells = gpd.sjoin(grid, wells_gdf, how='right')
    mywells = gridwells.loc[:, ['NAME', 'XCOORDS', 'YCOORDS', 'I', 'J']]
    mywells = mywells[~mywells.index.duplicated(keep='first')]

    mywells.columns = ['NAME', 'X', 'Y', 'Row', 'Col']
    print('finished joining geodataframes')
    df2csv = mywells.copy()
    df2csv.reset_index(inplace=True)
    print(df2csv.head())
    print(df2csv.columns)
    # df2csv.to_csv(os.path.join("input", "monitoring_wells_coords_ij.csv"), index=False)  # export CSV
    return mywells

## import data from calibration period 2014 - 2020.
def import_prior_data(mywells):   ## wells input can be any list of well names to be fed into function when called

    path2data = "S:/AUS/CHPRC.C003.HANOFF/Rel.044/045_100AreaPT/d01_CY2021_datapack/0_Data/Water_Level_Data/DataPull_020222"
    prior_data_files = ['qryAWLNAWLN_2.txt', 'qryManAWLN.txt', 'qryManHEIS.txt']

    all_prior_data = {}
    for file in prior_data_files:
       # print(file.split("\\")[-1].split('.')[0]) ## extract filename directory and use as dict key
        k = file.split('.')[0]
        all_prior_data[k] = pd.read_csv(os.path.join(path2data, file), sep = '|', parse_dates=['EVENT']) #, index_col = 0, parse_dates=True)

    rebound_wells = {}
    for k in all_prior_data.keys():
        rebound_wells[k] = all_prior_data[k].loc[all_prior_data[k]['NAME'].isin(list(mywells['NAME'].unique()))]
        rebound_wells[k] = rebound_wells[k].loc[(rebound_wells[k]['EVENT'].dt.year.astype(str) >= '2014') &
                                                (rebound_wells[k]['EVENT'].dt.year.astype(str) <= '2020')]
        # rebound_wells[k] = rebound_wells[k].loc[rebound_wells[k]['EVENT'].dt.year.astype(str) <= '2020']

    prior_data = pd.concat([v for k, v in rebound_wells.items()])

    ### QA ts plots. Note that IF plotting thru 2022, 2 outlier manual measurements are present. Can be ignored.
    # for well in list(prior_data['NAME'].unique()):
    #     toplot = prior_data[prior_data['NAME'] == well]
    #     fig, ax = plt.subplots(figsize = (5,3))
    #     ax.scatter(toplot['EVENT'], toplot['VAL'], label = well)
    #     ax.legend(ncol = 2)
    #     plt.grid(True)

    return prior_data

def import_pumping_data():

    pumping_data = pd.read_csv(os.path.join(wdir, 'model_packages', 'hist_2014_Oct2023', 'mnw2',
                                            'wellratesdxhx_cy2014_oct2023.csv'))
    times = pd.read_csv(os.path.join(cwd, 'input', 'sp_2014_2023.csv'))
    cols = ['ID'] + list(times['start_date'])
    pumping_data.columns = cols
    pumping_data[['Short', 'Function', 'System']] = pumping_data['ID'].str.split('_', 2, expand=True)

    total_plot = False
    if total_plot:
        wellinfo = pd.read_csv(os.path.join(cwd, 'output', 'well_info', 'calib_2014_Oct2023', 'allwells_master.csv')) #missing this file for Oct 2023
        wellinfo[['Short', 'Function', 'System']] = wellinfo['ID'].str.split('_', 2, expand=True)

        rumwells = wellinfo.loc[wellinfo['Aquifer'] == 'RUM']['Short']
        subset = 'HX_RUM'  ## name any subset of interest (HX_RUM, HX_UNC, etc...)
        if subset == 'HX_RUM':
            hxrum = pumping_data.loc[pumping_data['System'] == 'HX'].loc[pumping_data['Short'].isin(list(rumwells))]
            hxrum.set_index('ID', inplace=True)

        ## calculate total hx rum pumping rates
        start_date = '1/1/2014'
        end_date = '7/1/2023'
        total = hxrum.loc[:,start_date:end_date].sum()
        total.index = pd.to_datetime(total.index)

        fig, ax = plt.subplots(figsize=(8,3))
        ax.plot(total.index, abs(total))
        plt.title("Total Extraction in 100-H RUM-2 Wells")
        plt.grid()
        plt.ylabel('Pumping Rate (m3/d)')
        # plt.savefig(os.path.join(cwd, 'output', 'pumping_plots', 'total_hx_rum.png'), bbox_inches='tight', dpi=400)
    else:
        pass


    individual_plots = True
    sdate = '2019-01-01'
    fs = 10
    plt.rc('xtick', labelsize=fs)
    plt.rc('ytick', labelsize=fs)

    if individual_plots:
        df = pumping_data.iloc[:,:-3].transpose()  ## clip to timeseries data and transpose
        df.columns = df.iloc[0]
        df.reset_index(inplace=True)
        df.drop(0, inplace=True)
        df.rename(columns={"index":"Date"}, inplace=True)
        df.Date = pd.to_datetime(df.Date)

        for well in df.columns[1:]:
            print(well)
            toplot = df[well] #m3/day
            gpm2m3d = (24 * 60) / 1 * 231 * (25.4 / 1000 / 1) ** 3  ## m3d2gpm=0.183453
            toplot_gpm = toplot / gpm2m3d
            fig, ax = plt.subplots(figsize=(9, 4))
            ax.plot(pd.to_datetime(df.Date), abs(toplot_gpm), ls = '--', label=f"{well}")
            ax.scatter(df.Date, abs(toplot_gpm), s=10)
            # if "_I_" in well:
            #     plt.title(f"Injection Rate in {well}")
            # elif "_E_" in well:
            #     plt.title(f"Extraction Rate in {well}")
            plt.legend(loc="upper right", fontsize=fs - 2)
            plt.grid()
            plt.ylabel('Pumping Rate (GPM)')
            plt.xlim([pd.to_datetime(sdate), max(df.Date)])
            plt.savefig(os.path.join(cwd, 'output', 'pumping_plots', 'individual_wells', f'{well}_pumping_{sdate[:4]}_2023.png'), bbox_inches='tight', dpi=400)
            plt.close()
    else:
        pass

    return None

def plot_pumping_data_bygroup(pmp_grpwells, version="100H"):

    figdir = os.path.join(cwd, 'output', 'pumping_plots', 'grp_wells')
    if not os.path.isdir(figdir):
        os.makedirs(figdir)

    pumping_data = pd.read_csv(os.path.join(wdir, 'model_packages', 'hist_2014_Oct2023', 'mnw2',
                                            'wellratesdxhx_cy2014_oct2023.csv'))
    times = pd.read_csv(os.path.join(cwd, 'input', 'sp_2014_2023.csv'))
    cols = ['ID'] + list(times['start_date'])
    pumping_data.columns = cols
    pumping_data[['Short', 'Function', 'System']] = pumping_data['ID'].str.split('_', 2, expand=True)

    sdate = '2019-01-01'
    df = pumping_data.iloc[:,:-3].transpose()  ## clip to timeseries data and transpose
    df.columns = df.iloc[0]
    df.reset_index(inplace=True)
    df.drop(0, inplace=True)
    df.rename(columns={"index":"Date"}, inplace=True)
    df.Date = pd.to_datetime(df.Date)

    fs = 10
    plt.rc('xtick', labelsize=fs)
    plt.rc('ytick', labelsize=fs)
    cnt=0
    for wellgrp in pmp_grpwells:
        cnt += 1
        fig, ax = plt.subplots(figsize=(9, 4))
        for well in wellgrp:
            print(well)
            toplot = df[well]  # m3/day
            toplot_gpm = toplot / gpm2m3d
            ax.plot(pd.to_datetime(df.Date), abs(toplot_gpm), ls = '--', label=f"{well}")
            ax.scatter(df.Date, abs(toplot_gpm), s=10)
        # if "_I_" in well:
        #     plt.title(f"Injection Rate in {well}", fontsize=fs)
        # elif "_E_" in well:
        #     plt.title(f"Extraction Rate in {well}", fontsize=fs)
        plt.legend(loc="upper right", fontsize=fs - 2)
        ax.minorticks_on()
        ax.grid(which='major', linestyle='-',
                linewidth='0.1', color='k', alpha=0.85)
        ax.grid(which='minor', linestyle=':',
                linewidth='0.1', color='k', alpha=0.65)
        plt.xticks(rotation=45)
        plt.ylabel('Pumping Rate (GPM)')
        plt.xlim([pd.to_datetime(sdate), max(df.Date)])
        if version == "100D":
            ax.axvline(pd.to_datetime('2023-04-12'), color='gray', linestyle='-', linewidth=1, zorder=1)
        else: #100H
            ax.axvline(pd.to_datetime('2022-10-04'), color='gray', linestyle='-', linewidth=1, zorder=1)
        plt.savefig(os.path.join(figdir, f'grp{cnt}_pumping_{sdate[:4]}_2023.png'), bbox_inches='tight', dpi=400)
        plt.close()

    return None

def generate_plots(df_sp, myHds):

    ## calib wells used in plotting to identify which wells were used for model calibration
    calibwells = pd.read_csv(os.path.join(cwd, 'input', 'well_list_v3_for_calibration.csv'))

    for well in df_sp.index.get_level_values('ID').unique():
        toplot = df_sp.xs(well, level='ID')
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(toplot.index.get_level_values('Date'), toplot['Water Level (m)'], c = 'darkred',
                label = 'Observed - Resampled Monthly')
        df = myHds.loc[(myHds.Layer == 1) & (myHds.NAME == well)]
        dates = pd.to_datetime("2014-01-01") + pd.to_timedelta(df.Time, unit="days")
        ax.plot(dates, df.Head, label = f"Simulated", color = "cornflowerblue")
        is_in_calibwells = well in calibwells['Well_ID'].values
        if is_in_calibwells:
            ax.set_title(f'{well}', color = 'red')
        else:
            ax.set_title(f'{well}', color = 'black')
        ax.set_ylabel('Water Level (m)')
        ax.minorticks_on()
        grid = True
        if grid:
            ax.grid(which='major', linestyle='-',
                    linewidth='0.1', color='red')
            ax.grid(which='minor', linestyle=':',
                    linewidth='0.1', color='black')
        else:
            print("grid is OFF")
            pass
        ax.legend()
        plt.xticks(rotation = 45)
        fig.tight_layout()
        ax.set_xlim(pd.to_datetime("2014-01-01"), pd.to_datetime("2023-07-31"))
        ax.set_ylim([112.8,118])
        # plt.savefig(os.path.join('output', 'water_level_plots', f'{sce}', 'monthly resampled', f'{well}.png'))
    # plt.close()

    return None

if __name__ == "__main__":

    cwd = os.getcwd()
    gpm2m3d = (24 * 60) / 1 * 231 * (25.4 / 1000 / 1) ** 3  ## m3d2gpm=0.183453
    # df, df_sp, df_sp_m = import_WL_data() ## run once at beginning of workflow
    # df_sp.to_csv(os.path.join(cwd, 'output', 'water_level_data', 'obs_2021_2023', 'measured_WLs_daily.csv'))

    # coordscsv = os.path.join(wdir, 'data', 'water_levels', "qryWellHWIS.txt") #dataframe with coords for monitoring wells
    # monitoring_wells = get_wells_ij(df, coordscsv)
    # monitoring_wells = pd.read_csv(os.path.join(cwd, 'input', 'monitoring_wells_coords_ij_100D_v2.csv'))

    # prior_data = import_prior_data(monitoring_wells)
    # prior_data.to_csv(os.path.join(cwd, 'output', 'water_level_data', 'obs_2014_2020', 'measured_WLs_2014to2020_daily_V2.csv'), index = False)

    # sce = 'calib_2014_Oct2023'
    # hds_file = os.path.join(os.path.dirname(cwd), 'mruns', f'{sce}', f'flow_{sce[-9:]}', '100hr3.hds')
    # myHds = read_head(hds_file, monitoring_wells)

    # import_pumping_data() #updated to Oct 2023

    pmp_grpwells = [["199-H3-25_E_HX","199-H3-26_E_HX","199-H4-86_E_HX","199-H4-4_E_HX",],
                    ["199-H3-27_I_HX","199-H4-17_I_HX",],
                    ["199-H3-22_E_HX","199-H3-29_E_HX",]]
    plot_pumping_data_bygroup(pmp_grpwells, version="100H")

    # generate_plots(df_sp, myHds)

### --- QC --- ###
##quick check for overlapping occurences##
# wells1, wells2, wells3 = list(dict1.keys()), list(dict2.keys()), list(dict3.keys())
# import itertools
# l = list(itertools.chain(wells1, wells2, wells3))
# from collections import Counter
# Counter(l)

## check resampled wls vs measured wls
# odir = os.path.join(cwd, 'output', 'water_level_plots', 'resampling_checks')
# if not os.path.isdir(odir):
#     os.makedirs(odir)
# for well in df['ID'].unique():
#     print(well)
#     raw = df[df['ID'] == well]
#     resampled = df_sp_m.xs(well, level='ID')
#     fig, ax = plt.subplots(figsize=(8, 5))
#     ax.scatter(raw.index, raw['Water Level (m)'], label = 'Observed - Raw')
#     ax.plot(resampled.index.get_level_values('Date'), resampled['Water Level (m)'], c = 'darkred',
#             label = 'Observed - Resampled Monthly')
#     ax.legend()
#     ax.grid()
#     plt.savefig(os.path.join(odir, f'{well}_monthly.png'))

