#=====================================================
import numpy as np
import null_deblend as nd
import utils
import pandas as pd
import matplotlib.pyplot as plt
import pylab
import matplotlib
import math
import skimage
import random
import corner
import dropbox
import extract_corner
import om10
import galsim
from astropy.utils.console import ProgressBar
#from corner import corner
#=====================================================

class SLRealizer(object):

    '''
    Generates the toy catalog, plots the lensed system, and deblends sources
    using the OM10 catalog and observation history provided in constructor.
    '''

    def __init__(self, catalog=None, observation=None):
        """
        Reads in a lens sample catalog and observation data.
        We assume lenses are OM10 lenses and observation file is a pandas df
        """
        self.catalog = catalog
        # TODO query outside class and make resulting matrix a parameter
        self.observation = observation
        self.num_systems = len(self.catalog.sample)
        self.num_obs = len(self.observation)

    def draw_lens_random_date(self, lensID, convolve=False, save_dir=None):
        """                                                                                                                   
        Draws a lens with the given lensID under randomly chosen observation conditions,
        and returns the properties of the observed lens as a dictionary
                
        """
        # Randomly select epoch ID
        epochIdx = random.randint(0, self.num_obs)
        img, obj = nd.draw_system(self.catalog.get_lens(lensID), \
                                               self.observation.loc[epochIdx], save_dir)
        # Now visualize the lens system at the epoch defined by epochIdx
        fig, axes = plt.subplots(2, figsize=(5, 10))
        axes[0].imshow(img.array, interpolation='none', aspect='auto')
        axes[0].set_title("TRUE MODEL IMAGE")
        params = nd.generate_row(self.catalog.get_lens(lensID), 
                                              self.observation.loc[epochIdx])
        # FIXIT check if float conversion necessary
        galaxy = galsim.Gaussian(flux=params['flux'], sigma=params['size'])\
                       .shift(float(params['x']), float(params['y']))\
                       .shear(e1=params['e1'], e2=params['e2'])
        # TODO make pixel scale globally configurable
        img = galaxy.drawImage(scale=0.2, method='no_pixel')
        axes[1].imshow(img.array, interpolation='none', aspect='auto')
        axes[1].set_title("EMULATED IMAGE")
        if save_dir is not None:
            plt.savefig(save_dir + 'deblending.png')
        return params
    
    def make_source_table(self, save_dir='../../../data/source_table.csv'):
        """
        Returns a source table generated from all the lens systems in the catalog
        under all the observation conditions in the observation history,
        and saves it as a .csv file.
        """
        print("Began making the source catalog.")
        # FIXIT do not hardcode
        # TODO psf_sigma --> psf_fwhm
        columns_list = ['MJD', 'filter', 'RA', 'RA_err', 'DEC', 'DEC_err', 'x', 'x_com_err', 'y', 'y_com_err', 'flux', 'flux_err', 'size', 'size_err', 'e1', 'e2', 'psf_sigma', 'sky', 'lensid']
        df = pd.DataFrame(columns=columns_list)
        #ellipticity_upper_limit = desc.slrealizer.get_ellipticity_cut()
        print("Number of systems: %d, number of observations: %d" %(self.num_systems, self.num_obs))
        # TODO get rid of nested for loop
        hsm_failed = 0
        with ProgressBar(self.num_obs) as bar:
            for j in xrange(self.num_obs):
                for i in xrange(self.num_systems):
                    #if self.catalog.sample[i]['ELLIP'] < ellipticity_upper_limit: # ellipticity cut : 0.5
                    params_dict = nd.generate_row(currLens=self.catalog.get_lens(self.catalog.sample[i]['LENSID']),\
                                                                currObs=self.observation.loc[j])
                    if params_dict == None:
                        hsm_failed += 1
                    else:
                        # FIXIT try not to use list comprehension...
                        vals_arr = np.array([params_dict[k] for k in columns_list])
                        df.loc[len(df)]= vals_arr
                bar.update()
        df.set_index('lensid', inplace=True)
        df.to_csv(save_dir, index=True)
        print("Done making the source table which has %d rows, after getting %d errors from HSM failure." %(len(df), hsm_failed))
#        desc.slrealizer.dropbox_upload(dir, 'source_catalog_new.csv')

    def make_object_table(self, source_table_dir='../../../data/source_table.csv', save_dir='../../../data/object_catalog.csv'):
        """
        Generates the object table from the given source table at source_table_dir
        by averaging the properties for each filter,
        and saves it into save_dir.
        """
        print("Reading in the source catalog...")
        df = pd.read_csv(source_table_dir)
        lensID = df['lensid']
        lensID = lensID.drop_duplicates().as_matrix()
        column_name = ['lensid', \
                       'u_flux', 'u_x', 'u_y', 'u_size', 'u_flux_err', 'u_x_com_err', 'u_y_com_err', 'u_size_err', 'u_e1', 'u_e2',\
                       'g_flux', 'g_x', 'g_y', 'g_size', 'g_flux_err', 'g_x_com_err', 'g_y_com_err', 'g_size_err', 'g_e1', 'g_e2', \
                       'r_flux', 'r_x', 'r_y', 'r_size', 'r_flux_err', 'r_x_com_err', 'r_y_com_err', 'r_size_err', 'r_e1', 'r_e2',\
                       'i_flux', 'i_x', 'i_y', 'i_size', 'i_flux_err', 'i_x_com_err', 'i_y_com_err', 'i_size_err', 'i_e1', 'i_e2',\
                       'z_flux', 'z_x', 'z_y', 'z_size', 'z_flux_err', 'z_x_com_err', 'z_y_com_err', 'z_size_err', 'z_e1', 'z_e2']
        source_table = pd.DataFrame(columns=column_name)
        # TODO collapse querying
        for lens in lensID:
            lens_row = [lens]
            lens_array = df.loc[df['lensid'] == lens]
            for b in ['u', 'g', 'r', 'i', 'z']:
                lens_row += utils.return_mean_properties(lens_array.loc[lens_array['filter'] == b])
            # TODO why is this check necessary?
            if np.isfinite(lens_row).all():
                source_table.loc[len(source_table)]= np.array(lens_row)
        source_table = source_table.dropna(how='any')
        source_table.to_csv(save_dir, index=False)
        print("Done making the object table.")
#        desc.slrealizer.dropbox_upload(save_dir, 'object_catalog_new.csv') #this uploads to the desc account

# TODO need to debug past this point.
           
    # after merging, change this one to deblend_test
    def deblend(self, lensID=None, null_deblend=True):
        """
        Given a lens system, this method deblends the source and plots the process of deblending.

        Parameters
        ---------
        lensID : int
        OM10 lens ID which can be used to identify the lensed system
        
        null_deblend : bool
        If true, assumes null deblender. Working deblender is currently not being supported
        """

        if null_deblend is False:
            print('Sorry, working deblender is not being supported.')
            return
        
        # Keep randomly selecting epochs until we get one that is not in the 'y' filter:
        filter = 'y'
        while filter == 'y':
            randomIndex = random.randint(0, 200)
            filter = self.observation[randomIndex][1]
        image2 = desc.slrealizer.plot_all_objects(self.observation[randomIndex], self.catalog.get_lens(lensID))
        print('##################### PLOTTING ALL SOURCES ##################################')
        desc.slrealizer.show_color_map(image2)
        flux, first_moment_x, first_moment_y, covariance_matrix = desc.slrealizer.null_deblend(image2)
        print('first:', flux, first_moment_x, first_moment_y, covariance_matrix)
        image = desc.slrealizer.null_deblend_plot(flux, first_moment_x, first_moment_y, covariance_matrix)
        print('##################### AFTER NULL DEBLENDING ##################################')
        desc.slrealizer.show_color_map(image)

    def generate_cornerplot(self, color='black', object_table_dir = '../data/object_catalog_galsim_noise.csv', option = None, params = None, range=None, overlap=None, normed=False, data=None, label=None):
        """
        Given a source table, this method plots the cornerplot. The user has to specify which attributes they want to look at.

        Parameters
        ----------
        option : list of string/strings
        Choose from size, position, color, ellipticity, and magnitude. The cornerplot will show the attribute that the user selected.
        If None, the user should specify the parameters(column names) in the source table.

        params : tuples of strings
        Names of columns in source_table that the user wants to see in the cornerplot.
        Only works when option is not specified.

        range : list of tuples for each plot
        Returns cornerplot (matplotlib.pyplot)
        """

        options = [None, 'size', 'x_position', 'y_position', 'color', 'ellipticity', 'magnitude', 'position', 'phi', 'custom']
        object_table = pd.read_csv(object_table_dir)
        if ((option is None) and (params is None)):
            print('either specify params or option. You can choose among :')
            print(options)
            print('or specify columns in the source table that you want to see in the cornerplot.')
            return
        elif 'custom' in option:
            print('custom input')
        elif option is not None:
            data, label = np.array([]), []
            for elem in option:
                if elem not in options:
                    print(elem, 'is not in the option')
                    return
                method_name = 'calculate_'+elem
                cur_data, cur_label = getattr(extract_corner, method_name)(object_table)
                data = np.append(data, cur_data)
                label.extend(cur_label)
            data = data.reshape(len(label), len(object_table)).transpose()
        else:
            data, label = desc.slrealizer.extract_features(object_table, params)
        if overlap is None:
            fig = corner.corner(data, labels=label, color=color, smooth=1.0, range=range, hist_kwargs=dict(normed=normed))
        else:
            fig = corner.corner(data, labels=label, color=color, smooth=1.0, range=range, fig=overlap, hist_kwargs=dict(normed=normed))
        return fig