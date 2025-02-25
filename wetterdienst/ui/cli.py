# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import functools
import json
import logging
import sys
from pprint import pformat
from typing import List

import click
import cloup
from click_params import StringListParamType
from cloup.constraints import If, RequireExactly, accept_none

from wetterdienst import Kind, Provider, Wetterdienst, __appname__, __version__
from wetterdienst.exceptions import ProviderError
from wetterdienst.provider.dwd.radar.api import DwdRadarSites
from wetterdienst.provider.eumetnet.opera.sites import OperaRadarSites
from wetterdienst.ui.core import get_stations, get_values, set_logging_level

log = logging.getLogger(__name__)

appname = f"{__appname__} {__version__}"

provider_opt = cloup.option_group(
    "Provider",
    click.option(
        "--provider",
        type=click.Choice(list(map(lambda p: p.name, Provider)), case_sensitive=False),
        required=True,
    ),
)

kind_opt = cloup.option_group(
    "Kind",
    click.option(
        "--kind",
        type=click.Choice(
            [Kind.OBSERVATION.name, Kind.FORECAST.name],
            case_sensitive=False,
        ),
        required=True,
    ),
)

debug_opt = click.option("--debug", is_flag=True)


def get_api(provider: str, kind: str):
    """
    Function to get API for provider and kind, if non found click.Abort()
    is casted with the error message

    :param provider:
    :param kind:
    :return:
    """
    try:
        api = Wetterdienst(provider, kind)
    except ProviderError as e:
        click.Abort(e.str)

    return api


def station_options(command):
    """
    Station options for cli, which can be used for stations and values endpoint

    :param command:
    :return:
    """
    arguments = [
        cloup.option("--parameter", type=StringListParamType(","), required=True),
        cloup.option("--resolution", type=click.STRING, required=True),
        cloup.option("--period", type=StringListParamType(",")),
        cloup.option_group("All stations", click.option("--all", "all_", is_flag=True)),
        cloup.option_group(
            "Station id filtering",
            cloup.option("--station", type=StringListParamType(",")),
        ),
        cloup.option_group(
            "Station name filtering",
            cloup.option("--name", type=click.STRING),
        ),
        cloup.option_group(
            "Latitude-Longitude rank/distance filtering",
            cloup.option(
                "--coordinates", metavar="LATITUDE,LONGITUDE", type=click.STRING
            ),
            cloup.option("--rank", type=click.INT),
            cloup.option("--distance", type=click.FLOAT),
            help="Provide --coordinates plus either --rank or --distance.",
        ),
        cloup.constraint(
            If("coordinates", then=RequireExactly(1), else_=accept_none),
            ["rank", "distance"],
        ),
        cloup.option_group(
            "BBOX filtering",
            cloup.option("--bbox", metavar="LEFT BOTTOM RIGHT TOP", type=click.STRING),
        ),
        cloup.option_group(
            "SQL filtering",
            click.option("--sql", type=click.STRING),
        ),
        cloup.constraint(
            RequireExactly(1),
            ["all_", "station", "name", "coordinates", "bbox", "sql"],
        ),
    ]
    return functools.reduce(lambda x, opt: opt(x), reversed(arguments), command)


@cloup.group("wetterdienst")
def cli():
    """
    Usage:

        wetterdienst (-h | --help)
        wetterdienst version
        wetterdienst info

        wetterdienst radar [--dwd=<dwd>] [--all=<all>] [--odim-code=<odim-code>] [--wmo-code=<wmo-code>] [--country-name=<country-name>]

        wetterdienst about coverage --provider=<provider> --kind=<kind> [--parameter=<parameter>] [--resolution=<resolution>] [--period=<period>]
        wetterdienst about fields --provider=dwd --kind=observation --parameter=<parameter> --resolution=<resolution> --period=<period> [--language=<language>]

        wetterdienst stations --provider=<provider> --kind=<kind> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --all=<all> [--target=<target>] [--format=<format>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst stations --provider=<provider> --kind=<kind> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --station=<station> [--target=<target>] [--format=<format>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst stations --provider=<provider> --kind=<kind> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --name=<name> [--target=<target>] [--format=<format>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst stations --provider=<provider> --kind=<kind> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --coordinates=<latitude,longitude> --rank=<rank> [--sql=<sql>] [--target=<target>] [--format=<format>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst stations --provider=<provider> --kind=<kind> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --coordinates=<latitude,longitude> --distance=<distance> [--target=<target>] [--format=<format>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst stations --provider=<provider> --kind=<kind> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --bbox=<left,lower,right,top> [--target=<target>] [--format=<format>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst stations --provider=<provider> --kind=<kind> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --sql=<sql> [--target=<target>] [--format=<format>] [--pretty=<pretty>] [--debug=<debug>]

        wetterdienst values --provider=<provider> --kind=<kind> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --all=<all> [--target=<target>] [--format=<format>] [--tidy=<tidy>] [--humanize=<humanize>] [--si-units=<si-units>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst values --provider=<provider> --kind=<kind> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --station=<station> [--target=<target>] [--format=<format>] [--tidy=<tidy>] [--humanize=<humanize>] [--si-units=<si-units>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst values --provider=<provider> --kind=<kind> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --name=<name> [--target=<target>] [--format=<format>] [--tidy=<tidy>] [--humanize=<humanize>] [--si-units=<si-units>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst values --provider=<provider> --kind=<kind> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --coordinates=<latitude,longitude> --rank=<rank>  [--sql=<sql>] [--target=<target>] [--format=<format>] [--tidy=<tidy>] [--humanize=<humanize>] [--si-units=<si-units>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst values --provider=<provider> --kind=<kind> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --coordinates=<latitude,longitude> --distance=<distance> [--target=<target>] [--format=<format>] [--tidy=<tidy>] [--humanize=<humanize>] [--si-units=<si-units>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst values --provider=<provider> --kind=<kind> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --bbox=<left,lower,right,top> [--target=<target>] [--format=<format>] [--tidy=<tidy>] [--humanize=<humanize>] [--si-units=<si-units>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst values --provider=<provider> --kind=<kind> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --sql=<sql> [--target=<target>] [--format=<format>] [--humanize=<humanize>] [--tidy=<tidy>] [--si-units=<si-units>] [--pretty=<pretty>] [--debug=<debug>]

    Options:
        --parameter=<parameter>               Parameter Set/Parameter, e.g. "kl" or "precipitation_height", etc.
        --resolution=<resolution>             Dataset resolution: "annual", "monthly", "daily", "hourly", "minute_10", "minute_1", for DWD Mosmix: type of mosmix, either 'small' or 'large'
        --period=<period>                     Dataset period: "historical", "recent", "now"
        --all=<all>                           Bool for all stations
        --station=<station>                   Comma-separated list of station identifiers
        --name=<name>                         Name of queried station
        --coordinates=<latitude,longitude>    Latitude-longitude pair for filtering by geoposition.
        --rank=<rank>                         Rank of nearby stations when filtering by geoposition.
        --distance=<distance>                 Maximum distance in km when filtering by geoposition.
        --bbox=<left,bottom,right,top>        Quadruple of left, bottom, right and top corners of bbox
        --sql=<sql>                           SQL filter to apply for stations
        --date=<date>                         Date for filtering data. Can be either a single date(time) or
                                              an ISO-8601 time interval, see https://en.wikipedia.org/wiki/ISO_8601#Time_intervals.
        --sql-values=<sql-values>             SQL query to apply to values
        --target=<target>                     Output target for storing data into different data sinks.
        --format=<format>                     Output format. [Default: json]
        --language=<language>                 Output language. [Default: en]
        --tidy                                Tidy DataFrame
        --humanize                            Humanize parameters
        --si-units                            Convert to SI units
        --pretty                              Pretty json with indent 4
        --debug                               Enable debug messages
        --listen=<listen>                     HTTP server listen address.
        --reload                              Run service and dynamically reload changed files
        -h --help                             Show this screen

    Examples requesting observation stations:

        # Get list of all stations for daily climate summary data in JSON format
        wetterdienst stations --provider=dwd --kind=observation --parameter=kl --resolution=daily

        # Get list of all stations in CSV format
        wetterdienst stations --provider=dwd --kind=observation --parameter=kl --resolution=daily --format=csv

        # Get list of specific stations
        wetterdienst stations --provider=dwd --kind=observation --resolution=daily --parameter=kl --station=1,1048,4411

        # Get list of specific stations in GeoJSON format
        wetterdienst stations --provider=dwd --kind=observation --resolution=daily --parameter=kl --station=1,1048,4411 --format=geojson

    Examples requesting forecast stations:

        wetterdienst stations --provider=dwd --kind=forecast --parameter=large --resolution=large

    Examples requesting observation values:

        # Get daily climate summary data for specific stations
        wetterdienst values --provider=dwd --kind=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411

        # Get daily climate summary data for specific stations in CSV format
        wetterdienst values --provider=dwd --kind=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411

        # Get daily climate summary data for specific stations in tidy format
        wetterdienst values --provider=dwd --kind=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411 --tidy

        # Limit output to specific date
        wetterdienst values --provider=dwd --kind=observation --parameter=kl --resolution=daily --period=recent --date=2020-05-01 --station=1048,4411

        # Limit output to specified date range in ISO-8601 time interval format
        wetterdienst values --provider=dwd --kind=observation --parameter=kl --resolution=daily --period=recent --date=2020-05-01/2020-05-05

        # The real power horse: Acquire data across historical+recent data sets
        wetterdienst values --provider=dwd --kind=observation --parameter=kl --resolution=daily --date=1969-01-01/2020-06-11

        # Acquire monthly data for 2020-05
        wetterdienst values --provider=dwd --kind=observation --parameter=kl --resolution=monthly --date=2020-05

        # Acquire monthly data from 2017-01 to 2019-12
        wetterdienst values --provider=dwd --kind=observation --parameter=kl --resolution=monthly --date=2017-01/2019-12 --station=1048,4411

        # Acquire annual data for 2019
        wetterdienst values --provider=dwd --kind=observation --parameter=kl --resolution=annual --date=2019 --station=1048,4411

        # Acquire annual data from 2010 to 2020
        wetterdienst values --provider=dwd --kind=observation --parameter=kl --resolution=annual --date=2010/2020

        # Acquire hourly data
        wetterdienst values --provider=dwd --kind=observation --parameter=air_temperature --resolution=hourly --period=recent --date=2020-06-15T12 --station=1048,4411

        # Acquire data for specific parameter and dataset
        wetterdienst values --provider=dwd --kind=observation --parameter=precipitation_height/precipitation_more,temperature_air_200/kl --resolution=hourly --period=recent --date=2020-06-15T12 --station=1048,4411

    Examples requesting forecast values:

        wetterdienst values --provider=dwd --kind=forecast --parameter=ttt,ff --resolution=large --station=65510

    Examples using geospatial features:

        # Acquire stations and readings by geoposition, request specific number of nearby stations.
        wetterdienst stations --provider=dwd --kind=observation --resolution=daily --parameter=kl --period=recent --coordinates=49.9195,8.9671 --rank=5
        wetterdienst values --provider=dwd --kind=observation --resolution=daily --parameter=kl --period=recent --date=2020-06-30 --coordinates=49.9195,8.9671 --rank=5

        # Acquire stations and readings by geoposition, request stations within specific distance.
        wetterdienst stations --provider=dwd --kind=observation --resolution=daily --parameter=kl --period=recent --coordinates=49.9195,8.9671 --distance=25
        wetterdienst values --provider=dwd --kind=observation --resolution=daily --parameter=kl --period=recent --date=2020-06-30 --coordinates=49.9195,8.9671 --distance=25

    Examples using SQL filtering:

        # Find stations by state.
        wetterdienst stations --provider=dwd --kind=observation --parameter=kl --resolution=daily --period=recent --sql="SELECT * FROM data WHERE state='Sachsen'"

        # Find stations by name (LIKE query).
        wetterdienst stations --provider=dwd --kind=observation --parameter=kl --resolution=daily --period=recent --sql="SELECT * FROM data WHERE lower(station_name) LIKE lower('%dresden%')"

        # Find stations by name (regexp query).
        wetterdienst stations --provider=dwd --kind=observation --parameter=kl --resolution=daily --period=recent --sql="SELECT * FROM data WHERE regexp_matches(lower(station_name), lower('.*dresden.*'))"

        # Filter values: Display daily climate observation readings where the maximum temperature is below two degrees celsius.
        wetterdienst values --provider=dwd --kind=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411 --sql-values="SELECT * FROM data WHERE temperature_air_max_200 < 2.0;"

        # Filter measurements: Same as above, but use tidy format.
        # FIXME: Currently, this does not work, see https://github.com/earthobservations/wetterdienst/issues/377.
        wetterdienst values --provider=dwd --kind=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411 --sql-values="SELECT * FROM data WHERE parameter='temperature_air_max_200' AND value < 2.0;" --tidy

    Examples for inquiring metadata:
        # FIXME: those currently don't work
        # Display list of available parameters (air_temperature, precipitation, pressure, ...)
        wetterdienst dwd about parameters

        # Display list of available resolutions (10_minutes, hourly, daily, ...)
        wetterdienst dwd about resolutions

        # Display list of available periods (historical, recent, now)
        wetterdienst dwd about periods

        # Display coverage/correlation between parameters, resolutions and periods.
        # This can answer questions like ...
        wetterdienst about coverage --provider=dwd --kind=observation

        # Tell me all periods and resolutions available for 'air_temperature'.
        wetterdienst about coverage --provider=dwd --kind=observation --parameter=air_temperature

        # Tell me all parameters available for 'daily' resolution.
        wetterdienst about coverage --provider=dwd --kind=observation --resolution=daily

    Examples for exporting data to files:

        # Export list of stations into spreadsheet
        wetterdienst stations --provider=dwd --kind=observation --parameter=kl --resolution=daily --period=recent --target=file://stations.xlsx

        # Shortcut command for fetching readings
        alias fetch="wetterdienst values --provider=dwd --kind=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411"

        # Export readings into spreadsheet (Excel-compatible)
        fetch --target="file://observations.xlsx"

        # Export readings into Parquet format and display head of Parquet file
        fetch --target="file://observations.parquet"

        # Check Parquet file
        parquet-tools schema observations.parquet
        parquet-tools head observations.parquet

        # Export readings into Zarr format
        fetch --target="file://observations.zarr"

    Examples for exporting data to databases:

        # Shortcut command for fetching readings
        alias fetch="wetterdienst values --provider=dwd --kind=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411"

        # Store readings to DuckDB
        fetch --target="duckdb:///dwd.duckdb?table=weather"

        # Store readings to InfluxDB
        fetch --target="influxdb://localhost/?database=dwd&table=weather"

        # Store readings to CrateDB
        fetch --target="crate://localhost/?database=dwd&table=weather"

    Invoke the HTTP REST API service:

        # Start service on standard port, listening on http://localhost:7890.
        wetterdienst restapi

        # Start service on standard port and watch filesystem changes.
        # This is suitable for development.
        wetterdienst restapi --reload

        # Start service on public interface and specific port.
        wetterdienst restapi --listen=0.0.0.0:8890

    Invoke the Wetterdienst Explorer UI service:

        # Start service on standard port, listening on http://localhost:7891.
        wetterdienst explorer

        # Start service on standard port and watch filesystem changes.
        # This is suitable for development.
        wetterdienst explorer --reload

        # Start service on public interface and specific port.
        wetterdienst explorer --listen=0.0.0.0:8891

    """
    pass


@cli.command("info")
def info():
    from wetterdienst import info

    info()

    return


@cli.command("version")
def version():
    print(__version__)

    return


@cli.command("restapi")
@cloup.option("--listen", type=click.STRING, default=None)
@cloup.option("--reload", is_flag=True)
@debug_opt
def restapi(listen: str, reload: bool, debug: bool):
    set_logging_level(debug)

    # Run HTTP service.
    log.info(f"Starting {appname}")
    log.info(f"Starting HTTP web service on http://{listen}")

    from wetterdienst.ui.restapi import start_service

    start_service(listen, reload=reload)

    return


@cli.command("explorer")
@cloup.option("--listen", type=click.STRING, default=None)
@cloup.option("--reload", is_flag=True)
@debug_opt
def explorer(listen: str, reload: bool, debug: bool):
    set_logging_level(debug)

    log.info(f"Starting {appname}")
    log.info(f"Starting Explorer web service on http://{listen}")
    from wetterdienst.ui.explorer.app import start_service

    start_service(listen, reload=reload)
    return


@cli.group()
def about():
    pass


@about.command()
@cloup.option_group(
    "Provider",
    click.option(
        "--provider",
        type=click.Choice(list(map(lambda p: p.name, Provider)), case_sensitive=False),
    ),
)
@cloup.option_group(
    "Kind",
    click.option(
        "--kind",
        type=click.Choice(
            [Kind.OBSERVATION.name, Kind.FORECAST.name],
            case_sensitive=False,
        ),
    ),
)
@cloup.option("--filter", "filter_", type=click.STRING, default=False)
@debug_opt
def coverage(provider, kind, filter_, debug):
    set_logging_level(debug)

    if not provider or not kind:
        return json.dumps(Wetterdienst.discover(), indent=4)

    api = get_api(provider=provider, kind=kind)

    cov = api.discover(
        filter_=filter_,
        flatten=False,
    )

    print(cov)

    return


@about.command("fields")
@provider_opt
@kind_opt
@cloup.option_group(
    "(DWD only) information from PDF documents",
    click.option("--dataset", type=StringListParamType(",")),
    click.option("--resolution", type=click.STRING),
    click.option("--period", type=StringListParamType(",")),
    click.option("--language", type=click.Choice(["en", "de"], case_sensitive=False)),
    constraint=cloup.constraints.require_all,
)
@debug_opt
def fields(provider, kind, dataset, resolution, period, language, **kwargs):
    api = get_api(provider, kind)

    if not (
        api.provider == Provider.DWD and api.kind == Kind.OBSERVATION
    ) and kwargs.get("fields"):
        raise click.BadParameter("'fields' command only available for provider 'DWD'")

    metadata = api.describe_fields(
        dataset=dataset,
        resolution=resolution,
        period=period,
        language=language,
    )

    output = pformat(dict(metadata))

    print(output)

    return


@cli.command("stations")
@provider_opt
@kind_opt
@station_options
@cloup.option_group(
    "Format/Target",
    click.option(
        "--format",
        "fmt",
        type=click.Choice(["json", "geojson", "csv"], case_sensitive=False),
        default="json",
    ),
    cloup.option("--target", type=click.STRING),
)
@cloup.constraint(
    If("coordinates", then=RequireExactly(1), else_=accept_none),
    ["rank", "distance"],
)
@cloup.option("--pretty", is_flag=True)
@debug_opt
def stations(
    provider: str,
    kind: str,
    parameter: List[str],
    resolution: str,
    period: List[str],
    all_: bool,
    station: List[str],
    name: str,
    coordinates: str,
    rank: int,
    distance: float,
    bbox: str,
    sql: str,
    fmt: str,
    target: str,
    pretty: bool,
    debug: bool,
):
    set_logging_level(debug)

    api = get_api(provider=provider, kind=kind)

    stations_ = get_stations(
        api=api,
        parameter=parameter,
        resolution=resolution,
        period=period,
        date=None,
        issue=None,
        all_=all_,
        station_id=station,
        name=name,
        coordinates=coordinates,
        rank=rank,
        distance=distance,
        bbox=bbox,
        sql=sql,
        tidy=False,
        si_units=False,
        humanize=False,
    )

    if stations_.df.empty:
        log.error("No stations available for given constraints")
        sys.exit(1)

    if target:
        stations_.to_target(target)
        return

    indent = None
    if pretty:
        indent = 4

    output = stations_.to_format(fmt, indent=indent)

    print(output)

    return


@cli.command("values")
@provider_opt
@kind_opt
@station_options
@cloup.option("--date", type=click.STRING)
@cloup.option("--tidy", is_flag=True)
@cloup.option("--sql-values", type=click.STRING)
@cloup.option_group(
    "Format/Target",
    cloup.option(
        "--format",
        "fmt",
        type=click.Choice(["json", "csv"], case_sensitive=False),
        default="json",
    ),
    cloup.option("--target", type=click.STRING),
    help="Provide either --format or --target.",
)
@cloup.option("--issue", type=click.STRING)
@cloup.option("--si-units", type=click.BOOL, default=True)
@cloup.option("--humanize", type=click.BOOL, default=True)
@cloup.option("--pretty", is_flag=True)
@debug_opt
def values(
    provider: str,
    kind: str,
    parameter: List[str],
    resolution: str,
    period: List[str],
    date: str,
    issue: str,
    all_: bool,
    station: List[str],
    name: str,
    coordinates: str,
    rank: int,
    distance: float,
    bbox: str,
    sql: str,
    sql_values,
    fmt: str,
    target: str,
    tidy: bool,
    si_units: bool,
    humanize: bool,
    pretty: bool,
    debug: bool,
):
    set_logging_level(debug)

    api = get_api(provider, kind)

    try:
        values_ = get_values(
            api=api,
            parameter=parameter,
            resolution=resolution,
            period=period,
            date=date,
            issue=issue,
            all_=all_,
            station_id=station,
            name=name,
            coordinates=coordinates,
            rank=rank,
            distance=distance,
            bbox=bbox,
            sql=sql,
            sql_values=sql_values,
            si_units=si_units,
            tidy=tidy,
            humanize=humanize,
        )
    except ValueError as ex:
        log.exception(ex)
        sys.exit(1)
    else:
        if values_.df.empty:
            log.error("No data available for given constraints")
            sys.exit(1)

    if target:
        values_.to_target(target)
        return

    indent = None
    if pretty:
        indent = 4

    output = values_.to_format(fmt, indent=indent)

    print(output)

    return


@cli.command("radar")
@cloup.option("--dwd", is_flag=True)
@cloup.option("--all", "all_", is_flag=True)
@cloup.option("--odim-code", type=click.STRING)
@cloup.option("--wmo-code", type=click.STRING)
@cloup.option("--country-name", type=click.STRING)
@cloup.constraint(
    RequireExactly(1),
    ["dwd", "all_", "odim_code", "wmo_code", "country_name"],
)
def radar(
    dwd: bool,
    all_: bool,
    odim_code: str,
    wmo_code: str,
    country_name: str,
):
    if dwd:
        data = DwdRadarSites().all()
    else:
        if all_:
            data = OperaRadarSites().all()
        elif odim_code:
            data = OperaRadarSites().by_odimcode(odim_code)
        elif wmo_code:
            data = OperaRadarSites().by_wmocode(wmo_code)
        elif country_name:
            data = OperaRadarSites().by_countryname(country_name)

    output = json.dumps(data, indent=4)

    print(output)

    return


if __name__ == "__main__":
    cli()
