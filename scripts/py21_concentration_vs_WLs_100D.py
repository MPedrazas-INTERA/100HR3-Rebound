#%%
"""
Plotting functions:
Simulated and observed water levels + simulated and observed Cr(VI) concentrations timeseries
Scatter plots of simulated and observed water levels
Residual/error plots of observed-simulated vs observed water levels
"""

import numpy as np
import os
import flopy.utils.binaryfile as bf
import pandas as pd
import matplotlib.pyplot as plt
import flopy
import geopandas as gpd
import sys
import matplotlib
import matplotlib.patheffects as pe
matplotlib.use('Qt5Agg')
from sklearn.metrics import mean_absolute_error,  mean_squared_error, r2_score
from datetime import datetime

plt.rc('xtick', labelsize=14)
plt.rc('ytick', labelsize=14)

def read_head(sce, ifile_hds, df, all_lays=False):

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
    df_return.to_csv(os.path.join('output', 'water_level_data', f'{sce}', "simulated_heads_monthly_flopy.csv"), index=False)
    return df_return

def compare_flopy_mod2obs():
    ### QA: Compare wls from flopy to mod2obs
    ## Simulated WL, 2014 to 2023 [MONTHLY/SPs], using FLOPY
    wls_sim_flopy = pd.read_csv(os.path.join(wldir, f'{sce}', 'simulated_heads_monthly_flopy.csv'))
    wls_sim_flopy['DATE'] = pd.to_datetime("2014-01-01") + pd.to_timedelta(wls_sim_flopy.Time, unit="days")

    for well in wls_sim_flopy['NAME'].unique():
        fig, ax = plt.subplots(figsize=(7,4))
        fplot = wls_sim_flopy[wls_sim_flopy['NAME'] == well]
        mplot = wls_sim_SP[(wls_sim_SP['NAME'] == well) & (wls_sim_SP['Layer'] == 1)]
        ax.plot(fplot['DATE'], fplot['Head'], label = 'flopy')
        ax.plot(mplot['DATE'], mplot['Head'], label = 'mod2obs')
        # ax.scatter(fplot['Head'].iloc[:-1], mplot['Head']) ## scatter
        ax.legend()
        ax.grid()
        plt.title(f'{well}')
        plt.savefig(os.path.join(cwd, 'output', 'water_level_plots', 'flopy_vs_mod2obs', f'{well}_lyr1.png'), bbox_inches='tight', dpi=600)
    return None

def plot_WL_vs_conc(wl_meas, crvi_meas, wl_df, wl_df_2014, conc_df, plot_calib_model = False):

    """
    Plot concentration data of interest against water levels in one graph.
    May be used to plot either measured data or simulation results.
    Inputs: water level dataframe, concentration dataframe, data type
    dtype options: simulated, measured, or both. Simply to control style.
    Common errors: double check column names (e.g. "NAME" vs "ID", "time" vs "Date", etc.)
        rename columns outside of function for consistency.
    """
    outputDir = os.path.join(cwd, 'output', 'concentration_vs_WL_plots_100D', f'{sce}', "untilJan2024")
    if not os.path.isdir(outputDir):
        os.makedirs(outputDir)

    ## date range to plot (TOGGLE):
    date_range = "full" #"short" #"full

    for well in wells['NAME']: #["199-H3-10"]:
        print(well)
        toplot_wl = wl_df.loc[(wl_df['NAME'] == well) & (wl_df['Layer'] == (wells.Aq.loc[wells.NAME == well].iloc[0]))]  ## Simulated Monthly WLs from EXTENDED MODEL

        if plot_calib_model:
            toplot_wl2 = wl_df_2014.loc[(wl_df_2014['NAME'] == well) & (wl_df_2014['Layer'] == (wells.Aq.loc[wells.NAME == well].iloc[0]))]  ## Simulated Monthly WLs from CALIBRATED MODEL from FLOPY

        toplot_crvi = conc_df[conc_df['NAME'] == well] ## match to the correct input when function is called

        try:
            cr1 = crvi_meas.loc[crvi_meas['SAMP_SITE_NAME'] == well]  ## match to the correct input when function is called
        except:
            cr1 = crvi_meas.loc[crvi_meas['NAME'] == well]

        try:
            wl1 = wl_meas[wl_meas['ID'] == well]
        except:
            wl1 = wl_meas[wl_meas['NAME'] == well]

        if old_WL_sources:
            wl2 = calib_WLdata[calib_WLdata['ID'] == well]
            wl3 = wls_obs_2022[wls_obs_2022['ID'] == well]

        ## create figure instance and set specs
        fig, ax = plt.subplots(figsize=(16, 5))
        ax.minorticks_on()
        ax.grid(which='major', linestyle='-',
                linewidth='0.1', color='k', alpha=0.85)
        ax.grid(which='minor', linestyle=':',
                linewidth='0.1', color='k', alpha=0.65)
        plt.xticks(rotation=45)
        ## conditional title color
        is_in_calibwells = well in calibwells['Well_ID'].values
        if is_in_calibwells:
            ax.set_title(f'{well}', color = 'navy', fontsize=16)
        else:
            ax.set_title(f'{well}', color = 'black', fontsize=16)
        ax.set_ylabel('Water Level Elevation, m NAVD88', fontsize=14)
        ax2 = ax.twinx() ## create secondary axis
        ax2.set_ylabel('Cr(VI) (μg/L)', fontsize=14)

        ###HEADS
        try:
            ax.scatter(wl1.index, wl1['Water Level (m)'], label='Obs WL', c="navy", s=20, zorder=5)
            ax.plot(wl1.index, wl1['Water Level (m)'], c="navy", ls="--", alpha=0.25, zorder=5)
        except:
            ax.scatter(wl1.index, wl1['VAL_FINAL'], label='Obs WL', c="navy", s=20, zorder=5)
            ax.plot(wl1.index, wl1['VAL_FINAL'], c="navy", ls="--", alpha=0.25, zorder=5)

        if old_WL_sources:
            ax.scatter(wl3.index, wl3['Water Level (m)'], c="navy", s=20, zorder=5)
            ax.plot(wl3.index, wl3['Water Level (m)'], c="navy", ls="--", alpha=0.25, zorder=5)

            ax.scatter(wl2.index, wl2['Water Level (m)'], c="navy", s=20, zorder=5)
            ax.plot(wl2.index, wl2['Water Level (m)'], c="navy", ls="--", alpha=0.25, zorder=5)

        ax.plot(toplot_wl.index, toplot_wl['Head'], label='Simulated WL', color="cornflowerblue", zorder=4)
        if plot_calib_model:
            ax.plot(toplot_wl2.index, toplot_wl2['Head'], label='2014-2020 Model', color="orange", ls='--', zorder=5, alpha=0.25)

        ax.set_ylim([112.8,121])

        ###CONCENTRATION
        ax2.scatter(pd.to_datetime(cr1.index), cr1['STD_VALUE_RPTD'], c='crimson', s=20, zorder=5,
                    label='Obs Cr(VI)')  #
        ax2.plot(pd.to_datetime(cr1.index), cr1['STD_VALUE_RPTD'], zorder=10, c="crimson",
                 ls="--", alpha=0.25)

        ax2.plot(pd.to_datetime(toplot_crvi['DATE']), toplot_crvi['WeightedConc'], zorder=4,
                 c="darkred", alpha = 0.75,  label='Simulated Cr(VI)')

        # Add vertical lines at specified dates
        ax.axvline(pd.to_datetime('2021-01-01'), color='gray', linestyle='-', linewidth=1, zorder=2)
        ax.axvline(pd.to_datetime('2023-04-12'), color='gray', linestyle='-', linewidth=1, zorder=2)

        # Add horizontal lines at specified dates
        ax2.axhline(10, color='gray', alpha = 1, linestyle='-.', linewidth=1, label='10 μg/L', zorder=1)
        ax2.axhline(48, color='gray', alpha = 1, linestyle='-.', linewidth=1, label='48 μg/L', zorder=1)

        ## combined legend (+ fix order)
        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        index_10_ug = labels2.index('10 μg/L') # Legend items in wrong order - manual fix
        index_48_ug = labels2.index('48 μg/L') # Legend items in wrong order - manual fix
        reordered_labels2 = [l for l in labels2 if l not in ['10 μg/L', '48 μg/L']] + ['10 μg/L','48 μg/L']
        reordered_lines2 = [lines2[index] for index in range(len(lines2)) if
                           labels2[index] not in ['10 μg/L', '48 μg/L']] + [lines2[index_10_ug],lines2[index_48_ug]]
        ax2.legend(lines + reordered_lines2, labels + reordered_labels2, bbox_to_anchor=(1.2, 1), framealpha=1)
        
        # watermark
        text_label = datetime.now()
        ax.text(0.96, 0.02, text_label, transform=ax.transAxes, horizontalalignment='right', verticalalignment='bottom', alpha=0.1)
        text_y = ax2.get_ylim()[1] - 0.035 * (ax2.get_ylim()[1] - ax2.get_ylim()[0]) # for text annotations
        
        if date_range == "full": #set x-limit
            ax.set_xlim(pd.to_datetime("2014-01-01"), pd.to_datetime("2024-02-01"))
            ax2.set_xlim(pd.to_datetime("2014-01-01"), pd.to_datetime("2024-02-01"))
            ax2.text(pd.to_datetime('2021-02-01'), text_y, 'Post-Calibration Period', ha='left', va='top', rotation=90, color='k', alpha=0.75, path_effects=[pe.withStroke(linewidth=4, foreground='white')], zorder=10)
            ax2.text(pd.to_datetime('2023-06-12'), text_y, 'Rebound Period', ha='right', va='top', rotation=90, color='k', alpha=0.75, path_effects=[pe.withStroke(linewidth=4, foreground='white')], zorder=10)
            ax2.text(pd.to_datetime('2020-12-01'), text_y, 'Calibration Period', ha='right', va='top', rotation=90, color='k', alpha=0.75, path_effects=[pe.withStroke(linewidth=4, foreground='white')], zorder=10)
            plt.savefig(os.path.join(outputDir, f'{well}_mod2obs_2014to2024.png'), bbox_inches='tight')
        elif date_range == "short":
            ax.set_xlim(pd.to_datetime("2021-01-01"), pd.to_datetime("2024-02-01"))
            ax2.set_xlim(pd.to_datetime("2021-01-01"), pd.to_datetime("2024-02-01"))
            ax2.text(pd.to_datetime('2022-09-15'), text_y, 'Post-Calibration Period', ha='left', va='top', rotation=90, color='k', alpha=0.75, path_effects=[pe.withStroke(linewidth=4, foreground='white')], zorder=10)
            ax2.text(pd.to_datetime('2023-06-12'), text_y, 'Rebound Period', ha='right', va='top', rotation=90, color='k', alpha=0.75, path_effects=[pe.withStroke(linewidth=4, foreground='white')], zorder=10)
            plt.savefig(os.path.join(outputDir, f'{well}_mod2obs_2021to2024.png'), bbox_inches='tight')

        plt.close()
    print("Done")

    return None

def plot_WL(sce, wl_meas, wl_meas2, wl_meas_2022, wl_df, wl_df_2014, plot_calib_model = True):

    """
    Plot WL - simulated + observed.
    May be used to plot either measured data or simulation results.
    Inputs: water level dataframe, cdata type
    dtype options: simulated, measured, or both. Simply to control style.
    Common errors: double check column names (e.g. "NAME" vs "ID", "time" vs "Date", etc.)
        rename columns outside of function for consistency.
    """
    outputDir = os.path.join(cwd, 'output', 'water_level_plots', sce)
    if not os.path.isdir(outputDir):
        os.makedirs(outputDir)

    for well in wells['NAME']:  #["199-H3-10"]: #
        print(well)
        ## set data to be plotted
        toplot_wl = wl_df.loc[(wl_df['NAME'] == well) & (wl_df['Layer'] == (wells.Aq.loc[wells.NAME == well].iloc[0]))]  ## Simulated Monthly WLs from EXTENDED MODEL

        if plot_calib_model:
            # toplot_wl2 = wl_df_2014[wl_df_2014['Well'] == well]  ## Simulated Monthly WLs from CALIBRATED MODEL from an SSPA xlsx
            toplot_wl2 = wl_df_2014.loc[(wl_df_2014['NAME'] == well) & (wl_df_2014['Layer'] == (wells.Aq.loc[wells.NAME == well].iloc[0]))]  ## Simulated Monthly WLs from CALIBRATED MODEL from FLOPY

        wl1 = wl_meas[wl_meas['ID'] == well] #CLIENT FROM DATA
        wl2 = wl_meas2[wl_meas2['ID'] == well] #DATA FROM 2014 TO 2020 (100APT)
        wl3 = wl_meas_2022[wl_meas_2022['ID'] == well] #DATA FROM CY2022 (corrected)

        ## create figure instance and set specs
        fig, ax = plt.subplots(figsize=(15, 5))
        ax.minorticks_on()
        ax.grid(which='major', linestyle='-',
                linewidth='0.1', color='red')
        ax.grid(which='minor', linestyle=':',
                linewidth='0.1', color='black')
        plt.xticks(rotation=45)
        ## conditional title color
        is_in_calibwells = well in calibwells['Well_ID'].values
        if is_in_calibwells:
            ax.set_title(f'{well} ({wellDict[well]})', color = 'navy', fontsize=16)
        else:
            ax.set_title(f'{well} ({wellDict[well]})', color = 'black', fontsize=16)
        ax.set_ylabel('Water Level (m.asl)', fontsize=14)

        ###SIMULATED DATA FROM MODELS
        ax.plot(toplot_wl.index, toplot_wl['Head'], label='Simulated WL', color="darkgreen")
        if plot_calib_model:
            # ax.plot(pd.to_datetime(toplot_wl2.Time), toplot_wl2['Simulated'], label='Simulated WL (Calib)', color="orange", ls='--', zorder=20)
            ax.plot(toplot_wl2.index, toplot_wl2['Head'], label='Simulated WL (Calib)', color="orange", ls='--', zorder=100)


        ax.plot(wl3.index, wl3['Water Level (m)'], c="navy", ls="--")
        ax.scatter(wl3.index, wl3['Water Level (m)'], c="navy", s=15, label = "Obs WL")

        ax.scatter(pd.to_datetime(wl2.index), wl2['Water Level (m)'], c="navy", s=15,)
        ax.plot(pd.to_datetime(wl2.index), wl2['Water Level (m)'], c="navy", ls="--")

        ax.scatter(wl1.index, wl1['Water Level (m)'], label='Obs WL (Client)', c="red", s=15)
        ax.plot(wl1.index, wl1['Water Level (m)'], c="red", ls="--")

        ax.legend(loc='best')
        ax.set_xlim(pd.to_datetime("2014-01-01"), pd.to_datetime("2023-07-31"))
        # ax.set_xlim(pd.to_datetime("2021-01-01"), pd.to_datetime("2023-07-31"))
        plt.savefig(os.path.join(outputDir, f'{well}_V3_flopy_2014_2023_AllOBS.png'), bbox_inches='tight')
        plt.close()
    print("Done")

    return None

def crossplots_WL_individual(wls_obs, wls_obs2, wls_sim, mode):

    """
    Generates a crossplot of simulated vs observed water levels (or other variable of interest)
    at discrete time points.
    """
    # plt.rc('xtick', labelsize=14)
    # plt.rc('ytick', labelsize=14)

    outputDir = os.path.join(cwd, 'output', 'water_level_plots', 'crossplots')
    if not os.path.isdir(outputDir):
        os.makedirs(outputDir)
    for well in wells.NAME.unique():
        # print(well)
        ## set data to be plotted
        mywell_obs = wls_obs[wls_obs['ID'] == well]  ## 2021 - 2023
        mywell_obs2 = wls_obs2[wls_obs2['NAME'] == well]  ## 2014 - 2020
        mywell_sim = wls_sim[wls_sim['NAME'] == well]  ## extended model covers 2014 - 2023

        toplot = pd.merge(mywell_obs, mywell_sim, left_index=True, right_index=True, how="inner")
        toplot.rename(columns={"Head": "Simulated", "Water Level (m)": "Observed"}, inplace=True)
        toplot.dropna(subset=["Observed"], inplace=True)

        toplot2 = pd.merge(mywell_obs2, mywell_sim, left_index=True, right_index=True, how="inner")
        toplot2.rename(columns={"Head": "Simulated", "VAL": "Observed"}, inplace=True)
        toplot2.dropna(subset=["Observed"], inplace=True)

        fig, ax = plt.subplots(figsize=(10, 10))
        ax.plot(toplot['Observed'], toplot['Simulated'], 'o', markerfacecolor="steelblue", markeredgecolor='blue', markeredgewidth=1,
                markersize=10, alpha =0.3, zorder=1, label = '2021 - 2023')
        try:
            ax.plot(toplot2['Observed'], toplot2['Simulated'], 'o', markerfacecolor="olive", markeredgecolor='darkgreen', markeredgewidth=1,
                markersize=8, alpha =0.3, zorder=1, label = '2014 - 2020')
        except:
             print(f"{well} not found in 2014-2020 observations")
        ax.plot([0, 1], [0, 1], color='red', linewidth=0.5, transform=ax.transAxes, zorder=10)

        ## conditional title color
        is_in_calibwells = well in calibwells['Well_ID'].values
        if is_in_calibwells:
            ax.set_title(f'{well} ({wellDict[well]})', color='navy', fontweight='bold', fontsize=14)
        else:
            ax.set_title(f'{well} ({wellDict[well]})', color='black', fontweight='bold', fontsize=14)

        ax.set_ylabel('Simulated Head 2021-2023 (m)', fontweight='bold', fontsize=14)
        ax.set_xlabel('Observed Head 2021-2023 (m)', fontweight='bold', fontsize=14)
        ax.set_xlim([112.8, 121])
        ax.set_ylim([112.8, 121])

        ax.minorticks_on()
        ax.grid(which='major', linestyle='-',
                linewidth='0.1', color='darkred')
        ax.grid(which='minor', linestyle=':',
                linewidth='0.1', color='black')
        plt.xticks(rotation=45)
        ax.legend(loc="lower right")

        ### Add Statistics
        # r2 = r2_score(toplot['Observed'], toplot["Simulated"]).round(3)  # r2:coefficient of determination
        mae_2021 = mean_absolute_error(toplot["Observed"], toplot["Simulated"]).round(3)
        ax.text(113, 117.5, f'MAE 2021 - 2023 = {mae_2021} m', fontsize=14)
        # ax.text(113, 117.75, '$\mathregular{r^2}$ = ' + str(r2), fontsize=14)

        try:
            mae_2014 = mean_absolute_error(toplot2["Observed"], toplot2["Simulated"]).round(3)
            ax.text(113, 117.2, f'MAE 2014 - 2020 = {mae_2014} m', fontsize=14)
        except:
            pass

        plt.savefig(os.path.join(outputDir, f'{well}_{mode}.png'), bbox_inches='tight')
        plt.close()
        print("Done")
    return None

def crossplots_WL_subplots(wls_obs, wls_obs2, wls_sim, wls_sim2):

    """
    Generates grouped crossplots of simulated vs observed water levels (or other variable of interest)
    at discrete time points. Groups determined geospatially (riverside to inland, proximity to sources)
    """
    plt.rc('xtick', labelsize=14)
    plt.rc('ytick', labelsize=14)

    outputDir = os.path.join(cwd, 'output', 'water_level_plots', 'crossplots')
    if not os.path.isdir(outputDir):
        os.makedirs(outputDir)

    group1 = ['199-H3-25', '199-H3-26', '199-H3-27']  ## Inland
    group2 = ['199-H3-2A', '199-H4-86']  ## Inland near 100-H-46 source
    group3 = [ '199-H4-84', '199-H4-88']  ## Midland near 183-H-SEB source
    group4 = ['199-H4-8', '199-H4-17', '199-H4-18', '199-H4-65', '199-H4-85', '199-H4-89'] ## Midland
    group5 = ['199-H4-4', '199-H4-5', '199-H4-12A', '199-H4-15A', '199-H4-64'] ## Riverside
    groups = [group1, group2, group3, group4,group5] #

    for val, grp in enumerate(groups):
        size = len(grp)
        if size == 6:
            fig, axes = plt.subplots(nrows=2, ncols=3, gridspec_kw={'width_ratios': [1,1,1]},
                                     figsize=(14, 8), sharex=False, sharey=False)
        if size == 5:
            fig, axes = plt.subplots(nrows=2, ncols=3, gridspec_kw={'width_ratios': [1,1,1]},
                                     figsize=(14, 8), sharex=False, sharey=False)
        elif size == 4:
            fig, axes = plt.subplots(nrows=2, ncols=2, gridspec_kw={'width_ratios': [1,1]},
                                     figsize=(14, 8), sharex=False, sharey=False)
        elif size == 3:
            fig, axes = plt.subplots(nrows=1, ncols=3, gridspec_kw={'width_ratios': [1,1,1]},
                                     figsize=(14, 4), sharex=False, sharey=False)
        elif size == 2:
            fig, axes = plt.subplots(nrows=1, ncols=2, gridspec_kw={'width_ratios': [1,1]},
                                     figsize=(9, 4), sharex=False, sharey=False)
        else:
            pass

        axes = axes.flatten()
        fig.suptitle('Groundwater Levels', fontweight='bold', fontsize = 14)
        for i, well in enumerate(grp):
            ax = axes[i]
            print("Well: ",well)
            flag = "True"
            for idx in range(2):
                print("Idx: ",idx)
                if idx == 0:
                    mywell_obs = wls_obs.loc[wls_obs['ID'] == well]
                    # wls_sim.index = wls_sim["DATE"]
                    mywell_sim = wls_sim[wls_sim['NAME'] == well]
                    toplot = pd.merge(mywell_obs, mywell_sim, left_index=True, right_index=True, how="inner")
                    toplot.rename(columns={"Head": "Simulated", "Water Level (m)": "Observed"}, inplace=True)
                    toplot.dropna(subset=["Observed"], inplace=True)
                elif idx == 1:
                    try:
                        mywell_sim = wls_sim2[wls_sim2['Well'] == well]
                        mywell_obs = wls_obs2.loc[wls_obs2['Well'] == well]
                        toplot = pd.merge(mywell_obs, mywell_sim, on="Time", how="inner")
                        toplot.dropna(subset=["Observed"], inplace=True)
                        print("Found: ",idx, well, len(toplot))
                        if len(toplot) == 0:
                            flag = "NA"
                    except:
                        print(f"{well} not found in 2014-2020 observations from MPR")
                        flag = "NA"
                        print("Not Found: ", idx, well, len(toplot))

                if idx == 0:
                    ax.plot(toplot['Observed'], toplot['Simulated'], 'o', markerfacecolor="steelblue", markeredgecolor='blue',
                            markeredgewidth=1, markersize=10, alpha=0.5, zorder=9, label = "2021 to 2023")
                    ax.plot([0, 1], [0, 1], color='red', linewidth=0.5, transform=ax.transAxes, zorder=10)
                elif idx == 1 and (flag != "NA"):
                    ax.plot(toplot['Observed'], toplot['Simulated'], 'o', markerfacecolor="olive", markeredgecolor='darkgreen',
                            markeredgewidth=1, markersize=10, alpha=0.5, zorder=8, label = "2014 to 2020")
                    ax.plot([0, 1], [0, 1], color='red', linewidth=0.5, transform=ax.transAxes, zorder=10)

                ### Add Statistics
                if idx == 0:
                    print("P5 stat: ",len(toplot))
                    r2 = r2_score(toplot['Observed'], toplot["Simulated"]).round(3)  # r2:coefficient of determination
                    mae = mean_absolute_error(toplot["Observed"], toplot["Simulated"]).round(3)
                    ax.text(113, 117.5, '2021 - 2022: ' + '$\mathregular{r^2}$ = ' + str(r2), fontsize=9)
                    ax.text(113, 117, '2021 - 2022: ' + f'MAE = {mae} m', fontsize=9)
                elif idx == 1 and (flag != "NA"):
                    r2 = r2_score(toplot['Observed'], toplot["Simulated"]).round(3)  # r2:coefficient of determination
                    mae = mean_absolute_error(toplot["Observed"], toplot["Simulated"]).round(3)
                    ax.text(113, 116.5, '2014 - 2020: ' + '$\mathregular{r^2}$ = ' + str(r2), fontsize=9)
                    ax.text(113, 116, '2014 - 2020: ' + f'MAE = {mae} m', fontsize=9)

            ### conditional title color
            is_in_calibwells = well in calibwells['Well_ID'].values
            if is_in_calibwells:
                ax.set_title(f'{well} ({wellDict[well]})', color='navy', fontsize=14)
            else:
                ax.set_title(f'{well} ({wellDict[well]})', color='black', fontsize=14)

            ax.set_ylabel('Simulated (m)', fontsize=14)
            ax.set_xlabel('Observed (m)', fontsize=14)
            ax.label_outer()
            ax.set_xlim([112.8, 121])
            ax.set_ylim([112.8, 121])

            ax.minorticks_on()
            ax.grid(which='major', linestyle='-',
                    linewidth='0.1', color='darkred')
            ax.grid(which='minor', linestyle=':',
                    linewidth='0.1', color='black')
            # plt.xticks(rotation=45)
            ax.legend(loc="lower right")

            # Hide any remaining empty subplots
        for i in range(len(groups), len(axes)):
            if len(toplot) == 0:
                fig.delaxes(axes[i])
            else:
                pass
        fig.tight_layout()

        plt.savefig(os.path.join(outputDir, f'grp{val+1}_V5.png'), bbox_inches='tight', dpi=600)

        plt.close()
        print("Done")

    return None

def residualplots_WL_individual(wls_obs, wls_obs2, wls_sim):

    outputDir = os.path.join(cwd, 'output', 'water_level_plots', 'residual_plots', f"{sce}", f'{area}')
    if not os.path.isdir(outputDir):
        os.makedirs(outputDir)

    for well in wells.NAME.unique(): #["199-H4-84"]: # #["199-H4-84"]:#:
        aq = wells.Aq.loc[(wells.NAME == well)].iloc[0]
        print(well, aq)
        ## set data to be plotted
        if old_WL_sources:
            rebound = wls_obs.loc[wls_obs['ID'] == well]  ## 10/4/22 to 10/31/23
            postcalib = wls_obs.loc[wls_obs['ID'] == well]  ## 01/01/2021 to 10/3/22
            calib = wls_obs2.loc[wls_obs2['ID'] == well]  ## 01/01/14 -12/31/2020

        else:
            rebound = wls_obs.loc[wls_obs['ID'] == well]
            postcalib = rebound.copy()
            calib = rebound.copy()

        simulated = wls_sim.loc[(wls_sim['NAME'] == well) & (wls_sim['Layer'] == aq)]

        #Rebound Data
        rebound = rebound.loc[(rebound.index >= pd.to_datetime("10-04-2022"))]
        plot_rebound = pd.merge(rebound, simulated, left_index=True, right_index=True, how="inner")
        plot_rebound.rename(columns={"Head": "Simulated", "Water Level (m)": "Observed"}, inplace=True)
        plot_rebound.dropna(subset=["Observed"], inplace=True)
        plot_rebound['Residual'] = plot_rebound['Observed'] - plot_rebound['Simulated']

        #Post-Calib Data
        postcalib = postcalib.loc[(postcalib.index >= pd.to_datetime("01-01-2021")) & (postcalib.index < pd.to_datetime("10-04-2022"))]
        plot_postcalib = pd.merge(postcalib, simulated, left_index=True, right_index=True, how="inner")
        plot_postcalib.rename(columns={"Head": "Simulated", "Water Level (m)": "Observed"}, inplace=True)
        plot_postcalib.dropna(subset=["Observed"], inplace=True)
        plot_postcalib['Residual'] = plot_postcalib['Observed'] - plot_postcalib['Simulated']

        #Calib Data:
        calib = calib.loc[(calib.index >= pd.to_datetime("01-01-2014")) & (calib.index < pd.to_datetime("01-01-2021"))]
        plot_calib = pd.merge(calib, simulated, left_index=True, right_index=True, how="inner")
        plot_calib.rename(columns={"Head": "Simulated", "Water Level (m)": "Observed"}, inplace=True)
        plot_calib.dropna(subset=["Observed"], inplace=True)
        plot_calib['Residual'] = plot_calib['Observed'] - plot_calib['Simulated']

        fig, ax = plt.subplots(figsize=(10, 5))
        try:
            ax.plot(plot_rebound['Observed'], plot_rebound['Residual'], 'o', markerfacecolor="steelblue", markeredgecolor='blue',
                    markeredgewidth=1, markersize=10, alpha=0.5, zorder = 2, label="Rebound Study")
        except:
            pass
        try:
            ax.plot(plot_postcalib['Observed'], plot_postcalib['Residual'], 'o', markerfacecolor="mediumorchid",
                        markeredgecolor='purple',
                        markeredgewidth=1, markersize=8, alpha=0.3, zorder = 2, label="Post-Calibration")
        except:
            pass
        try:
            ax.plot(plot_calib['Observed'], plot_calib['Residual'], 'o', markerfacecolor="olive",
                        markeredgecolor='darkgreen',
                        markeredgewidth=1, markersize=8, alpha=0.3, zorder = 2, label="Calibration")
        except:
            pass
        ax.axhline(y=0, color='r', linestyle='-', zorder = 1)

        ## conditional title color
        is_in_calibwells = well in calibwells['Well_ID'].values
        if is_in_calibwells:
            ax.set_title(f'{well}', color='navy', fontweight='bold', fontsize=14)
        else:
            ax.set_title(f'{well}', color='black', fontweight='bold', fontsize=14)

        ax.set_ylabel('Observed - Simulated (m)', fontweight='bold', fontsize=14)
        ax.set_xlabel('Observed Head (m)', fontweight='bold', fontsize=14)
        ax.set_xlim([116, 121])
        ax.set_ylim([-3,3])

        ax.minorticks_on()
        ax.grid(which='major', linestyle='-',
                linewidth='0.1', color='darkred')
        ax.grid(which='minor', linestyle=':',
                linewidth='0.1', color='black')
        ax.legend(loc="upper right")

        # watermark
        text_label = datetime.now()
        ax.text(0.96, 0.02, text_label, transform=ax.transAxes, horizontalalignment='right', verticalalignment='bottom', alpha=0.1)

        if mode == "monthly":
            plt.savefig(os.path.join(outputDir, f'{well}.png'), bbox_inches='tight', dpi=600)
        elif mode == "daily":
            plt.savefig(os.path.join(outputDir, f'{well}_daily.png'), bbox_inches='tight', dpi=600)
        plt.close()

    print("Done")
    return None

def residualplots_WL_subplots(wls_obs, wls_obs2, wls_sim):

    """
    Note that the statistical definition of residuals is the difference between actual and fitted values.
    So technically speaking, observed - simulated = residual for the calibration period only.
    The difference between actual and **forecasted** values is the error.
    So observed - simulated = error for the validation period.
    See: https://en.wikipedia.org/wiki/Errors_and_residuals
    """

    outputDir = os.path.join(cwd, 'output', 'water_level_plots', 'residual_plots')
    if not os.path.isdir(outputDir):
        os.makedirs(outputDir)

    group1 = ['199-H3-25', '199-H3-26', '199-H3-27']  ## Inland
    group2 = ['199-H3-2A', '199-H4-86']  ## Inland near 100-H-46 source
    group3 = ['199-H4-84', '199-H4-88']  ## Midland near 183-H-SEB source
    group4 = ['199-H4-8', '199-H4-17', '199-H4-18', '199-H4-65', '199-H4-85', '199-H4-89']  ## Midland
    group5 = ['199-H4-4', '199-H4-5', '199-H4-12A', '199-H4-15A', '199-H4-64']  ## Riverside
    groups = [group1, group2, group3, group4, group5]  #

    for val, grp in enumerate(groups):
        size = len(grp)
        if size == 6:
            fig, axes = plt.subplots(nrows=2, ncols=3, gridspec_kw={'width_ratios': [1, 1, 1]},
                                     figsize=(14, 8), sharex=False, sharey=False)
        if size == 5:
            fig, axes = plt.subplots(nrows=2, ncols=3, gridspec_kw={'width_ratios': [1, 1, 1]},
                                     figsize=(14, 8), sharex=False, sharey=False)
        elif size == 4:
            fig, axes = plt.subplots(nrows=2, ncols=2, gridspec_kw={'width_ratios': [1, 1]},
                                     figsize=(14, 8), sharex=False, sharey=False)
        elif size == 3:
            fig, axes = plt.subplots(nrows=1, ncols=3, gridspec_kw={'width_ratios': [1, 1, 1]},
                                     figsize=(14, 4), sharex=False, sharey=False)
        elif size == 2:
            fig, axes = plt.subplots(nrows=1, ncols=2, gridspec_kw={'width_ratios': [1, 1]},
                                     figsize=(9, 4), sharex=False, sharey=False)
        else:
            pass

        axes = axes.flatten()
        fig.suptitle('Model Deviations', fontweight='bold', fontsize=14)
        for i, well in enumerate(grp):
            ax = axes[i]
            print("Well: ", well)
            mywell_obs = wls_obs.loc[wls_obs['ID'] == well]
           # wls_sim.index = wls_sim["DATE"]
            mywell_sim = wls_sim[wls_sim['NAME'] == well]
            toplot = pd.merge(mywell_obs, mywell_sim, left_index=True, right_index=True, how="inner")
            toplot.rename(columns={"Head": "Simulated", "Water Level (m)": "Observed"}, inplace=True)
            toplot.dropna(subset=["Observed"], inplace=True)
            toplot['Error'] = toplot['Observed'] - toplot['Simulated']
            mywell_sim2 = wls_sim[wls_sim['NAME'] == well]  ## using the extended model results (works for daily and monthly)
            mywell_obs2 = wls_obs2.loc[wls_obs2['NAME'] == well]
            toplot2 = pd.merge(mywell_obs2, mywell_sim2, left_index=True, right_index=True, how="inner")
            toplot2.rename(columns={"Head": "Simulated", "VAL": "Observed"}, inplace=True)
            toplot2.dropna(subset=["Observed"], inplace=True)
            toplot2['Residual'] = toplot2['Observed'] - toplot2['Simulated']
            print("Found: ", well, len(toplot2))

            ax.plot(toplot['Observed'], toplot['Error'], 'o', markerfacecolor="steelblue",
                    markeredgecolor='blue',
                    markeredgewidth=1, markersize=10, alpha=0.5, zorder=2, label="2021 to 2023")
            ax.axhline(y=0, color='r', linestyle='-', zorder = 1)

            try:
                ax.plot(toplot2['Observed'], toplot2['Residual'], 'o', markerfacecolor="olive",
                        markeredgecolor='darkgreen',
                        markeredgewidth=1, markersize=8, alpha=0.3, zorder=2, label="2014 to 2020")
            except:
                print("Not Found: ", well, len(toplot2))

            ### conditional title color
            is_in_calibwells = well in calibwells['Well_ID'].values
            if is_in_calibwells:
                ax.set_title(f'{well} ({wellDict[well]})', color='navy', fontsize=14)
            else:
                ax.set_title(f'{well} ({wellDict[well]})', color='black', fontsize=14)

            ax.set_ylabel('Observed - Simulated (m)', fontsize=14)
            ax.set_xlabel('Observed (m)', fontsize=14)
            ax.label_outer()
            ax.set_xlim([112.8, 121])
            ax.set_ylim(-3,3)

            ax.minorticks_on()
            ax.grid(which='major', linestyle='-',
                    linewidth='0.1', color='darkred')
            ax.grid(which='minor', linestyle=':',
                    linewidth='0.1', color='black')
            # plt.xticks(rotation=45)
            ax.legend(loc="lower right")

            # Hide any remaining empty subplots
        for i in range(len(groups), len(axes)):
            if len(toplot) == 0:
                fig.delaxes(axes[i])
            else:
                pass
        fig.tight_layout()

        plt.savefig(os.path.join(outputDir, f'grp{val+1}_deviations_daily.png'), bbox_inches='tight', dpi=600)

        plt.close()
        print("Done")
    return None

def resample_to_monthly(wells, df):
    """
    :param df: columns need to be named NAME/ID and EVENT/DATE
    :param woi: list of WELLS of interest
    :return: df_monthly
    """
    df.rename(columns={"EVENT":"DATE", "NAME":"ID", "VAL": "Water Level (m)"}, inplace=True)
    df.DATE = pd.to_datetime(df.DATE)
    df_monthly = pd.DataFrame()
    for well in wells.NAME.unique():
        try:
            mywell = df.loc[df.ID == well]
            mywell2 = mywell.resample('MS', on='DATE').mean() #MS is first day of month, M is last day of month.
            mywell2["ID"] = well
            df_monthly = df_monthly.append(mywell2)
        except:
            pass
    df_monthly.dropna(subset=["Water Level (m)"], inplace=True)
    return df_monthly

if __name__ == "__main__":

    area = '100D'

    cwd = os.getcwd()
    sce = "calib_2014_Oct2023"
    mdir = os.path.join(os.path.dirname(cwd), 'mruns')
    wldir = os.path.join(cwd, 'output', 'water_level_data')
    chemdir = os.path.join(cwd, 'output', 'concentration_data')

    times = pd.read_csv(os.path.join(cwd, 'input', 'sp_2014_2023.csv'))
    wells = pd.read_csv(os.path.join(cwd, 'input', 'monitoring_wells_coords_ij_100D_v2.csv')) # hpham updated
    calibwells = pd.read_csv(os.path.join(cwd, 'input', 'well_list_v3_for_calibration.csv')) # wells used to calibrate original 2014 - 2020 model

    ### SET WELL NAME ASSOCIATIONS ###
    #wellDict = {'199-H3-25': "North PT Sensor Data", '199-H3-26': "North PT Sensor Data", '199-H3-27': "North PT Sensor Data", '199-H3-2A': "North AWLN", '199-H4-12A': "North Manual",
    # '199-H4-15A': "North Manual", '199-H4-17': "North PT Sensor Data", '199-H4-18': "North Manual", '199-H4-4': "North PT Sensor Data", '199-H4-5': "North AWLN",
    # '199-H4-64': "North Manual", '199-H4-65': "North Manual", '199-H4-8': "North AWLN", '199-H4-84': "North AWLN", '199-H4-85': "North Manual",
    # '199-H4-86': "North PT Sensor Data", '199-H4-88': "North AWLN", '199-H4-89': "North Manual",
    # '199-H3-10': "RUM-2", '199-H3-12': "RUM-2", '199-H3-13': "RUM-2", '199-H3-30': "RUM-2", '199-H3-32': "RUM-2", '199-H4-90': "RUM-2"}
    
    wellDict = {'199-D1-1':'',
                '199-D2-11':'',
                '199-D2-14':'',
                '199-D5-15':'',
                '199-D5-17':'',
                '199-D5-33':'',
                '199-D5-34':'',
                '199-D5-37':'',
                '199-D5-39':'',
                '199-D5-41':'',
                '199-D5-43':'',
                '199-D5-44':'',
                '199-D5-103':'',
                '199-D5-104':'',
                '199-D5-106':'',
                '199-D5-123':'',
                '199-D5-128':'',
                '199-D5-133':'',
                '199-D5-142':'',
                '199-D5-145':'',
                '199-D5-146':'',
                '199-D5-149':'',
                '199-D5-150':'',
                '199-D5-151':'',
                '199-D5-152':'',
                '199-D5-160':'',
                'C6272':'',
                'AT-D-1-M':'',
                '35-S':''}


    #%%   ### IMPORT FILES ###

    ### WATER LEVELS
    old_WL_sources = False

    ### Monthly WL (obs and sim) for 2014 to 2020, from original calibration model:
    wl_2014 = pd.read_csv(
        os.path.join(wldir, "calib_2014_2020", "calib_2014to2020_obs_sim.csv"))  ###monthly/SP-averaged hpham: no need to change
    wl_meas_2014 = wl_2014[["Well", "Time", "Observed"]]
    #TODO: run flopy to get sim heads at 100D wells as input to the below (if we want):
    wl_sim_2014 = pd.read_csv(os.path.join(wldir, 'calib_2014_2020', 'simulated_heads_monthly_flopy.csv')) # hpham: No wells in 100-D, need to update? Do we need this? robin: only if we simulate heads with flopy (to compare with obs or with mod2obs)
    wl_sim_2014['DATE'] = pd.to_datetime("2013-12-01") + pd.to_timedelta(wl_sim_2014.Time,
                                                                         unit="days")  # subtracted one month to match how we resample to monthly using MS, which is first day of the month.
    if old_WL_sources: # hpham: This is no longer used.
        ### Observed WL for 2021 to Oct 2023: #This comes from script py08a_plot_water_levels.py
        new_wl_meas_monthly = pd.read_csv(os.path.join(wldir, 'obs_2021_Oct2023', 'measured_WLs_monthly_100D.csv'), index_col='Date', parse_dates=True) #hpham: Need to rm outlier
        new_wl_meas_daily = pd.read_csv(os.path.join(wldir, 'obs_2021_Oct2023', 'measured_WLs_daily_100D.csv'), index_col='Date', parse_dates=True)  #hpham: Need to rm outlier


        ### Daily obs raw WL data for 2014 to 2020
        ### [A] extracted from S:\AUS\CHPRC.C003.HANOFF\Rel.044\045_100AreaPT\d01_CY2021_datapack\0_Data\Water_Level_Data\DataPull_020222
        wl_meas_2014_daily = pd.read_csv(os.path.join(cwd, wldir, 'obs_2014_2020', 'measured_WLs_2014to2020_daily_V2.csv')) # Need to update
        wl_meas_2014_daily['EVENT'] = pd.to_datetime(wl_meas_2014_daily['EVENT']).dt.normalize()
        wl_meas_2014_daily.rename(columns={'EVENT':'DATE'}, inplace=True)
        wl_meas_2014_daily.set_index('DATE', inplace=True)

        #[B] ###MONTHLY 2014-2020 data from 100APT ECF.
        tmp = wl_meas_2014_daily[["NAME", "VAL"]].copy()
        tmp.reset_index(inplace=True)
        wls_obs_2014to2020_monthly = resample_to_monthly(wells, tmp)
        ###NOTE. I want to sample MONTHLY now from beginning, not from daily, but OK.

        ### MORE DATA (OBSERVATIONS)
        #[1] ###CY2022
        # [A] MONTHLY RUM-2022 data
        rum_2022 = pd.read_csv(os.path.join(os.path.dirname(cwd), 'data', 'water_levels', 'WaterLevel_CY2022', 'AllData_RUM_2022.csv')) #monthly OBS for CY2022 from HPham
        rum_2022 = rum_2022.loc[rum_2022.TYPE != "CP"]
        rum_2022.rename(columns = {"NAME": "ID", "VAL":"Water Level (m)"}, inplace=True)
        rum_2022["Datestring"] = "2022-" + rum_2022["EVENT"].astype(str) + "-01"
        rum_2022["DATE"] = pd.to_datetime(rum_2022["Datestring"])
        rum_2022.sort_values(by="DATE", inplace=True)
        rum_2022_monthly = rum_2022[["ID", "Water Level (m)", "DATE"]].copy()
        rum_2022_monthly.set_index('DATE', inplace=True) ###MONTHLY RUM-2022 data

        # [B] MONTHLY AWLN-2022 data
        awln_2022 = pd.read_csv(os.path.join(os.path.dirname(cwd), 'data', 'water_levels', 'WaterLevel_CY2022', 'awln_wl_cy2022.csv'))
        awln_2022_monthly = resample_to_monthly(wells, awln_2022)

        # [C] MONTHLY MANUAL-2022 data
        man_2022 = pd.read_csv(os.path.join(os.path.dirname(cwd), 'data', 'water_levels', 'WaterLevel_CY2022', 'manual_wl_cy2022.csv'))
        man_2022_monthly = resample_to_monthly(wells, man_2022)

        #[2] MERGE ALL 2022 OBSERVATIONS INTO ONE DATAFRAME
        wls_obs_2022 = pd.concat([rum_2022_monthly, awln_2022_monthly, man_2022_monthly], axis=0)
        wls_obs_2022 = wls_obs_2022.reset_index().drop_duplicates()
        wls_obs_2022.sort_values(by="DATE", inplace=True)
        wls_obs_2022.dropna(subset=["Water Level (m)"], inplace=True)
        wls_obs_2022.set_index('DATE', inplace=True)
    else:
        ### Kirsten's AWLN data + Jose's manual data + Sylvana's data (until Jan 2024) - RESAMPLED TO MONTHLY
        ### Script used: py21d_processWL_keep_all_wells.py (NOW) - py21c_processWL_fromJose.py (OLD)
        monthly_WLs_obs_ALL = pd.read_csv(os.path.join(wldir, 'obs_2014_Jan2024', 'measured_WLs_monthly_100D_wells.csv'), index_col='EVENT', parse_dates=True) # mpedrazas updated

    ## MOD2OBS simulated WL monthly (extended model):
    simulated_heads_mode = "mod2obs"
    mode = "monthly"
#%%
    if (simulated_heads_mode == 'mod2obs') and (mode == "monthly"):
        wls_sim_SP = pd.read_csv(os.path.join(wldir, f'{sce}', 'simulated_heads_monthly_100D.dat'), #this is renamed bore_sample_output.dat for flow #check 01/17/2024
                                 delimiter=r"\s+", names = ["ID", "Date", "Time", "Head"])
        wls_sim_SP["NAME"] = "199-" + wls_sim_SP["ID"].str.strip().str[:-3]  # monitoring wells
        wls_sim_SP["Layer"] = wls_sim_SP["ID"].str.strip().str[-1].astype(int)
        wls_sim_SP['Date'] = pd.to_datetime(wls_sim_SP['Date'])
        wls_sim_SP['Date'] = wls_sim_SP['Date'] - pd.DateOffset(months=1) #subtracted one month to match how we resample OBS to monthly using MS, which is first day of the month.
        wls_sim_SP.rename(columns={"Date": "DATE"}, inplace=True)
        ### MOD2OBS simulated WL DAILY (extended model):
    elif (simulated_heads_mode == 'mod2obs') and (mode == "daily"):
        wls_sim_daily = pd.read_csv(os.path.join(wldir, f'{sce}', 'simulated_heads_daily.dat'), delimiter=r"\s+",
                                    names=["ID", "Date", "Time", "Head"])
        wls_sim_daily["NAME"] = "199-" + wls_sim_daily["ID"].str.strip().str[:-3]  # monitoring wells
        wls_sim_daily["Layer"] = wls_sim_daily["ID"].str.strip().str[-1].astype(int)
        wls_sim_daily['Date'] = pd.to_datetime(wls_sim_daily['Date'])
        wls_sim_daily.rename(columns={"Date": "DATE"}, inplace=True)
    elif simulated_heads_mode == 'flopy':
        # hds_file = os.path.join(os.path.dirname(cwd), 'mruns', f'{sce}', f'flow_{sce[-9:]}', '100hr3.hds')
        # read_head(sce, hds_file, wells, all_lays=True)
        wls_sim_SP = pd.read_csv(os.path.join(wldir, f'{sce}', 'simulated_heads_monthly_flopy.csv'))
        wls_sim_SP['DATE'] = pd.to_datetime("2013-12-01") + pd.to_timedelta(wls_sim_SP.Time, unit="days") #subtracted one month to match how we resample OBS to monthly using MS, which is first day of the month.

    if (mode == "monthly") and old_WL_sources:
        rebound_WLdata = new_wl_meas_monthly #averaged by SP = monthly, client rebound data (+ post-calib)
        calib_WLdata = wls_obs_2014to2020_monthly #wl_meas_2014 (resampled to monthly)
        WLsim = wls_sim_SP
        WLsim_2014 = wl_sim_2014 #incase we want to plot SSPA calib model 2014-2020
    elif (mode == "monthly") and (old_WL_sources == False):
        WLsim = wls_sim_SP
        WLsim_2014 = wl_sim_2014 #incase we want to plot SSPA calib model 2014-2020
    elif (mode == "daily") and old_WL_sources:
        rebound_WLdata = new_wl_meas_daily
        calib_WLdata = wl_meas_2014_daily
        WLsim = wls_sim_daily
    else:
        sys.exit()


    ### CONCENTRATIONS ###
    ## Simulated CONC, 2014 to 2023 extended model:
    crvi_ifile = os.path.join(mdir, f'{sce}', f'tran_2014_2023', 'post_process',
                              'mod2obs_monitoring_wells_100D', 'simulated_conc_mod2obs_100D.csv') # hpham: updated
    crvi_sim = pd.read_csv(crvi_ifile)
    crvi_sim.rename(columns={'SAMP_SITE_NAME':'NAME','SAMP_DATE':'DATE'}, inplace = True)

    ### Observed CONC for 2014 to Oct 2023
    crvi_meas_2023 = pd.read_csv(os.path.join(chemdir, '2014to2023', '100D', 'Cr_obs_2014_2023_100D_mp.csv'), index_col = 'DATE', parse_dates = True)
    crvi_meas_2024 = pd.read_csv(os.path.join(chemdir, '2023to2024', '100D', 'Cr_obs_100D.csv'), index_col = 'DATE', parse_dates=True)
    crvi_meas_2024 = crvi_meas_2024.loc[crvi_meas_2024.index > pd.to_datetime(crvi_meas_2023.index.max())]
    ### I can't do the following because the dates matter, not only the months. So better to keep intact the 2023 dataset, and add the new 2024 obs.
    ### HP found minor differences when comparing the overlap.
    # crvi_meas_2024 = crvi_meas_2024.loc[crvi_meas_2024.index > pd.to_datetime("04/30/2023")]
    # crvi_meas_2023 = crvi_meas_2023.loc[crvi_meas_2023.index <= pd.to_datetime("04/30/2023")]
    crvi_meas_2024.rename(columns={"VAL": "STD_VALUE_RPTD"}, inplace=True)
    crvi_meas_ALL = pd.concat([crvi_meas_2023, crvi_meas_2024])
    crvi_meas_ALL.sort_index(inplace=True)

    ### Check to make sure everything in crvi_meas_2024 is the same as crvi_meas_2023:
    test_2023 = crvi_meas_2023[["NAME", "STD_VALUE_RPTD"]].loc[crvi_meas_2023.index > min(crvi_meas_2024.index)]
    test_2024 = crvi_meas_2024[["NAME", "STD_VALUE_RPTD"]].loc[crvi_meas_2024.index > min(crvi_meas_2024.index)]
    test_2023.sort_values(by=["NAME"], inplace=True)
    test_2024.sort_values(by=["NAME"], inplace=True)
    test_2023['YEAR'] = test_2023.index.year
    test_2023['MONTH'] = test_2023.index.month
    test_2024['YEAR'] = test_2024.index.year
    test_2024['MONTH'] = test_2024.index.month
    test_2023.reset_index(inplace=True, drop = True)
    test_2024.reset_index(inplace=True, drop=True)
    test_2023.sort_values(by=["STD_VALUE_RPTD"])
    test_2024.sort_values(by=["STD_VALUE_RPTD"])
    merged_df = pd.merge(test_2023, test_2024, on=['NAME', 'YEAR', 'MONTH'],
                         suffixes=('_2023', '_2024'), how='outer')
    different_rows = merged_df[merged_df['STD_VALUE_RPTD_2023'] != merged_df['STD_VALUE_RPTD_2024']]

    ## If we want to use average WL or max concentration of layers, group here:
    group = True
    ## + when rum2 wells are included in analysis
    rum2 = True
    if group:
        if rum2:
            temp = WLsim[WLsim['Layer'] <= 4]
            mywell_sim = temp.groupby(['DATE', 'NAME']).agg({'Head': 'mean'}).reset_index()
            mywell_sim['Layer'] = 'Unconfined'
            mywell_sim2 = WLsim[WLsim['Layer'] == 9]
            mywell_sim2['Layer'] = 'RUM-2'
            WLsim = pd.concat([mywell_sim, mywell_sim2])[['DATE', 'NAME', 'Head', 'Layer']]

            if mode == "monthly":
                temp = WLsim_2014[WLsim_2014['Layer'] <= 4] ###FloPy 2014-2020 model
                mywell_sim = temp.groupby(['DATE', 'NAME']).agg({'Head': 'mean'}).reset_index()
                mywell_sim['Layer'] = 'Unconfined'
                mywell_sim2 = WLsim_2014[WLsim_2014['Layer'] == 6] #2014-2020 model is 6-layered
                mywell_sim2['Layer'] = 'RUM-2'
                WLsim_2014 = pd.concat([mywell_sim, mywell_sim2])[['DATE', 'NAME', 'Head', 'Layer']]
        else:
            temp = WLsim[WLsim['Layer'] <= 4]
            mywell_sim = temp.groupby(['DATE', 'NAME']).agg({'Head': 'mean'}).reset_index()
            mywell_sim['Layer'] = 'Unconfined'
            WLsim = mywell_sim
            if mode == "monthly":
                temp = WLsim_2014[WLsim_2014['Layer'] <= 4] ###FloPy 2014-2020 model
                mywell_sim = temp.groupby(['DATE', 'NAME']).agg({'Head': 'mean'}).reset_index()
                mywell_sim['Layer'] = 'Unconfined'
                WLsim_2014 = mywell_sim
    else:
        pass

    WLsim.set_index('DATE', inplace=True)
    WLsim_2014.set_index('DATE', inplace=True)

    #%% ### PLOTTING

    ## Plot WLs and CONCs:
    if old_WL_sources:
        plot_WL_vs_conc(rebound_WLdata, calib_WLdata, crvi_meas_ALL, WLsim, WLsim_2014, crvi_sim, plot_calib_model=False)
        residualplots_WL_individual(rebound_WLdata, calib_WLdata, WLsim)
    else:
        plot_WL_vs_conc(monthly_WLs_obs_ALL, crvi_meas_ALL, WLsim, WLsim_2014, crvi_sim)
        residualplots_WL_individual(monthly_WLs_obs_ALL, monthly_WLs_obs_ALL, WLsim)

    # plot_WL(wls_obs, wls_obs2, wls_obs_2022, wls_sim, wls_sim2, plot_calib_model=True) #plot_calib_model flag should be FALSE if simulated_heads_mode == "mod2obs"

    ## Plot deviations

    # residualplots_WL_subplots(wls_obs, wls_obs2, wls_sim)

    ### Plot WLs scatterplots:
    #crossplots_WL_individual(wls_obs, wls_obs2, wls_sim, mode)
    # crossplots_WL_subplots(wls_obs, wls_obs2, wls_sim, wls_sim2)

