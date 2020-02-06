"""Functions for subsampling datasets.

"""

from collections import defaultdict
import numpy as np
import pandas as pd
from pymbar import timeseries


def _check_multiple_times(data):
    return data.sort_index(0).reset_index(0).duplicated('time').any()


def slicing(data, lower=None, upper=None, step=None, force=False):
    """Subsample an alchemlyb DataFrame using slicing on the outermost index (time).

    Slicing will be performed separately on groups of rows corresponding to
    each set of lambda values present in the DataFrame's index. Each group will
    be sorted on the outermost (time) index prior to slicing.

    Parameters
    ----------
    data : DataFrame
        DataFrame to subsample.
    lower : float
        Lower time to slice from.
    upper : float
        Upper time to slice to (inclusive).
    step : int
        Step between rows to slice by.
    force : bool
        Ignore checks that DataFrame is in proper form for expected behavior.

    Returns
    -------
    DataFrame
        `data` subsampled.

    """
    # we always start with a full index sort on the whole dataframe
    data = data.sort_index()

    index_names = list(data.index.names[1:])
    resdata = list()

    for name, group in data.groupby(level=index_names):
        group_s = group.loc[lower:upper:step]

        if not force and _check_multiple_times(group_s):
            raise KeyError("Duplicate time values found; it's generally advised "
                           "to use slicing on DataFrames with unique time values "
                           "for each row. Use `force=True` to ignore this error.")

        resdata.append(group_s)

    return pd.concat(resdata)


def statistical_inefficiency(data, how='auto', column=None, lower=None, upper=None, step=None,
                             conservative=True, return_calculated=False, force=False):
    """Subsample an alchemlyb DataFrame based on the calculated statistical inefficiency
    of one of its columns.

    Calculation of statistical inefficiency and subsequent subsampling will be
    performed separately on groups of rows corresponding to each set of lambda
    values present in the DataFrame's index. Each group will be sorted on the
    outermost (time) index prior to any calculation.

    The `how` parameter determines the observable used for calculating the
    correlations within each group of samples. The options are as follows:

        'auto' 
            The default; the approach is chosen from the below approaches based
            on the `alchemform` of the data (either 'dHdl' or 'u_nk'). Use this
            if in doubt.
        'right'
            The default for 'u_nk' datasets; the column immediately to the
            right of the column corresponding to the group's lambda index value
            is used. If there is no column to the right, then the column to the left is used.
            If there is no column corresponding to the group's lambda index
            value, then 'random' is used (see below).
        'left'
            The opposite of the 'right' approach; the column immediately to the
            left of the column corresponding to the group's lambda index value
            is used. If there is no column to the left, then the column to the
            right is used.  If there is no column corresponding to the group's
            lambda index value, then 'random' is used for that group (see below).
        'random'
            A column is chosen at random from the set of columns available in
            the group. If the correlation calculation fails, then another
            column is tried. This process continues until success or until all
            columns have been attempted without success.
        'sum'
            The default for 'dHdl' datasets; the columns are simply summed, and
            the resulting `Series` is used.

    Specifying the 'column' parameter overrides the behavior of 'how'. This
    allows the user to use a particular column or a specially-crafted `Series`
    for correlation calculation.

    Parameters
    ----------
    data : DataFrame
        DataFrame to subsample according statistical inefficiency of `series`.
    how : {'auto', 'right', 'left', 'random', 'sum'}
        The approach used to choose the observable on which correlations are
        calculated. See explanation above.
    column : label or `pandas.Series`
        Label of column to use for calculating statistical inefficiency.
        Overrides `how`; can also take a `Series` object, but the index of the
        `Series` *must* match that of `data` exactly.
    lower : float
        Lower time to pre-slice data from.
    upper : float
        Upper time to pre-slice data to (inclusive).
    step : int
        Step between rows to pre-slice by.
    conservative : bool
        ``True`` use ``ceil(statistical_inefficiency)`` to slice the data in uniform
        intervals (the default). ``False`` will sample at non-uniform intervals to
        closely match the (fractional) statistical_inefficieny, as implemented
        in :func:`pymbar.timeseries.subsampleCorrelatedData`.
    return_calculated : bool
        ``True`` return a tuple, with the second item a dict giving, e.g. `statinef`
        for each group.
    force : bool
        Ignore checks that DataFrame is in proper form for expected behavior.

    Returns
    -------
    DataFrame
        `data` subsampled according to subsampled `column`.

    Note
    ----
    For a non-integer statistical ineffciency :math:`g`, the default value
    ``conservative=True`` will provide _fewer_ data points than allowed by
    :math:`g` and thus error estimates will be _higher_. For large numbers of
    data points and converged free energies, the choice should not make a
    difference. For small numbers of data points, ``conservative=True``
    decreases a false sense of accuracy and is deemed the more careful and
    conservative approach.

    See Also
    --------
    pymbar.timeseries.statisticalInefficiency : detailed background
    pymbar.timeseries.subsampleCorrelatedData : used for subsampling


    .. versionchanged:: 0.4.0
       The ``series`` keyword was replaced with the ``column`` keyword.
       The function no longer takes an arbitrary series as input for
       calculating statistical inefficiency.

    .. versionchanged:: 0.2.0
       The ``conservative`` keyword was added and the method is now using
       ``pymbar.timeseries.subsampleCorrelatedData()``; previously, the statistical
       inefficiency was _rounded_ (instead of ``ceil()``) and thus one could
       end up with correlated data.

    """
    # we always start with a full index sort on the whole dataframe
    data = data.sort_index()

    index_names = list(data.index.names[1:])
    resdata = list()

    if return_calculated:
        calculated = defaultdict(dict)

    if column:

    for name, group in data.groupby(level=index_names):
            
        group_s = slicing(group, lower=lower, upper=upper, step=step)

        if not force and _check_multiple_times(group):
            raise KeyError("Duplicate time values found; statistical inefficiency"
                           "is only meaningful for a single, contiguous, "
                           "and sorted timeseries.")

        # calculate statistical inefficiency of column (could use fft=True but needs test)
        statinef = timeseries.statisticalInefficiency(group_s[column], fast=False)

        # use the subsampleCorrelatedData function to get the subsample index
        indices = timeseries.subsampleCorrelatedData(group_s[column], g=statinef,
                                      conservative=conservative)

        resdata.append(group_s.iloc[indices])

        if return_calculated:
            calculated['statinef'][name] = statinef
    
    if return_calculated:
        return pd.concat(resdata), calculated
    else:
        return pd.concat(resdata)


def equilibrium_detection(data, how='auto', column=None, lower=None, upper=None, step=None,
                          conservative=True, return_calculated=False, force=False):
    """Subsample a DataFrame using automated equilibrium detection on one of
    its columns.

    Equilibrium detection and subsequent subsampling will be performed
    separately on groups of rows corresponding to each set of lambda values
    present in the DataFrame's index. Each group will be sorted on the
    outermost (time) index prior to any calculation.

    The `how` parameter determines the observable used for calculating the
    correlations within each group of samples. The options are as follows:

        'auto' 
            The default; the approach is chosen from the below approaches based
            on the `alchemform` of the data (either 'dHdl' or 'u_nk'). Use this
            if in doubt.
        'right'
            The default for 'u_nk' datasets; the column immediately to the
            right of the column corresponding to the group's lambda index value
            is used. If there is no column to the right, then the column to the left is used.
            If there is no column corresponding to the group's lambda index
            value, then 'random' is used (see below).
        'left'
            The opposite of the 'right' approach; the column immediately to the
            left of the column corresponding to the group's lambda index value
            is used. If there is no column to the left, then the column to the
            right is used.  If there is no column corresponding to the group's
            lambda index value, then 'random' is used for that group (see below).
        'random'
            A column is chosen at random from the set of columns available in
            the group. If the correlation calculation fails, then another
            column is tried. This process continues until success or until all
            columns have been attempted without success.
        'sum'
            The default for 'dHdl' datasets; the columns are simply summed, and
            the resulting `Series` is used.

    Specifying the 'column' parameter overrides the behavior of 'how'. This
    allows the user to use a particular column or a specially-crafted `Series`
    for correlation calculation.

    Parameters
    ----------
    data : DataFrame
        DataFrame to subsample according to equilibrium detection on `series`.
    how : {'auto', 'right', 'left', 'random', 'sum'}
        The approach used to choose the observable on which correlations are
        calculated. See explanation above.
    column : label or `pandas.Series`
        Label of column to use for calculating statistical inefficiency.
        Overrides `how`; can also take a `Series` object, but the index of the
        `Series` *must* match that of `data` exactly.
    lower : float
        Lower time to pre-slice data from.
    upper : float
        Upper time to pre-slice data to (inclusive).
    step : int
        Step between rows to pre-slice by.
    conservative : bool
        ``True`` use ``ceil(statistical_inefficiency)`` to slice the data in uniform
        intervals (the default). ``False`` will sample at non-uniform intervals to
        closely match the (fractional) statistical_inefficieny, as implemented
        in :func:`pymbar.timeseries.subsampleCorrelatedData`.
    return_calculated : bool
        ``True`` return a tuple, with the second item a dict giving, e.g. `statinef`
        for each group.
    force : bool
        Ignore checks that DataFrame is in proper form for expected behavior.

    Returns
    -------
    DataFrame
        `data` subsampled according to subsampled `column`.

    Note
    ----
    For a non-integer statistical ineffciency :math:`g`, the default value
    ``conservative=True`` will provide _fewer_ data points than allowed by
    :math:`g` and thus error estimates will be _higher_. For large numbers of
    data points and converged free energies, the choice should not make a
    difference. For small numbers of data points, ``conservative=True``
    decreases a false sense of accuracy and is deemed the more careful and
    conservative approach.

    See Also
    --------
    pymbar.timeseries.detectEquilibration : detailed background
    pymbar.timeseries.subsampleCorrelatedData : used for subsampling


    .. versionchanged:: 0.4.0
       The ``series`` keyword was replaced with the ``column`` keyword.
       The function no longer takes an arbitrary series as input for
       calculating statistical inefficiency.

    .. versionchanged:: 0.4.0
       The ``conservative`` keyword was added and the method is now using
       ``pymbar.timeseries.subsampleCorrelatedData()``; previously, the statistical
       inefficiency was _rounded_ (instead of ``ceil()``) and thus one could
       end up with correlated data.

    """
    # we always start with a full index sort on the whole dataframe
    data = data.sort_index()

    index_names = list(data.index.names[1:])
    resdata = list()

    if return_calculated:
        calculated = defaultdict(dict)

    for name, group in data.groupby(level=index_names):
        group_s = slicing(group, lower=lower, upper=upper, step=step)

        if not force and _check_multiple_times(group):
            raise KeyError("Duplicate time values found; equilibrium detection "
                           "is only meaningful for a single, contiguous, "
                           "and sorted timeseries.")

        # calculate statistical inefficiency of series, with equilibrium detection
        t, statinef, Neff_max  = timeseries.detectEquilibration(group_s[column])

        # only keep values past `t`
        group_s = group_s.iloc[t:]

        # use the subsampleCorrelatedData function to get the subsample index
        indices = timeseries.subsampleCorrelatedData(group_s[column], g=statinef,
                                      conservative=conservative)

        resdata.append(group_s.iloc[indices])

        if return_calculated:
            calculated['t'][name] = statinef
            calculated['statinef'][name] = statinef
            calculated['Neff_max'][name] = statinef

    if return_calculated:
        return pd.concat(resdata), calculated
    else:
        return pd.concat(resdata)
