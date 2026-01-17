# Data Schema Reference

This document describes the data model used by the Morticia Sail Plan Tracker.

## InfluxDB Schema

### Measurement: `sail_config`

Each sail configuration change is stored as a point in the `sail_config` measurement.

#### Tags

| Tag | Type | Description |
|-----|------|-------------|
| `vessel` | string | Vessel identifier, always `"morticia"` |

#### Fields

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `main` | string | `DOWN`, `FULL`, `R1`, `R2`, `R3`, `R4` | Main sail state |
| `headsail` | string | `JIB`, `J1`, `STORM`, or `""` | Headsail selection (empty if none) |
| `downwind` | string | `BIGGEE`, `REACHING_SPI`, `WHOMPER`, or `""` | Downwind sail selection (empty if none) |
| `staysail_mode` | boolean | `true`, `false` | Whether jib is used as staysail with Reaching Spi |
| `comment` | string | freeform | Optional notes about conditions or reason for change |

#### Timestamp

Points are timestamped with second precision. The app uses the current UTC time unless the user backdates the entry.

### Example Point

```
sail_config,vessel=morticia main="FULL",headsail="JIB",downwind="",staysail_mode=false,comment="Starting conditions" 1705500000000000000
```

## Sail Inventory

### Main Sail States

| Value | Display | Description |
|-------|---------|-------------|
| `DOWN` | DN | Main sail furled/down |
| `FULL` | FULL | Full main, no reefs |
| `R1` | R1 | First reef |
| `R2` | R2 | Second reef |
| `R3` | R3 | Third reef |
| `R4` | R4 | Fourth reef (storm) |

### Headsails

| Value | Display | Description |
|-------|---------|-------------|
| `JIB` | Jib | Standard jib |
| `J1` | J1 | J1 headsail |
| `STORM` | Storm | Storm jib |

Headsails are mutually exclusive (only one can be set).

### Downwind Sails

| Value | Display | Description |
|-------|---------|-------------|
| `BIGGEE` | Biggee | Code 0 / Biggee |
| `REACHING_SPI` | R.Spi | Reaching spinnaker |
| `WHOMPER` | Whomp | Whomper |

Downwind sails are mutually exclusive (only one can be set).

### Special Combinations

**Staysail Mode**: When `REACHING_SPI` is selected, the `JIB` can be used simultaneously as a staysail. This is indicated by `staysail_mode=true`.

## Querying Data

### Flux Queries for Grafana

#### Basic Query - All Sail Changes

```flux
from(bucket: "default")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "sail_config")
  |> filter(fn: (r) => r["vessel"] == "morticia")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
```

#### Main Sail Changes Only

```flux
from(bucket: "default")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "sail_config")
  |> filter(fn: (r) => r["vessel"] == "morticia")
  |> filter(fn: (r) => r["_field"] == "main")
```

#### Count Changes by Sail Type

```flux
from(bucket: "default")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "sail_config")
  |> filter(fn: (r) => r["vessel"] == "morticia")
  |> filter(fn: (r) => r["_field"] == "main")
  |> group(columns: ["_value"])
  |> count()
```

#### Recent History with Comments

```flux
from(bucket: "default")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "sail_config")
  |> filter(fn: (r) => r["vessel"] == "morticia")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 20)
```

### InfluxDB CLI

#### Query Recent Entries

```bash
influx query '
from(bucket: "default")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sail_config")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
'
```

#### Delete Specific Entry

```bash
influx delete \
  --bucket default \
  --start 2025-01-17T12:00:00Z \
  --stop 2025-01-17T12:00:01Z \
  --predicate '_measurement="sail_config" AND vessel="morticia"'
```

## Signal K Integration

### Position Endpoint

The app fetches GPS position for timezone detection:

```
GET /signalk/v1/api/vessels/self/navigation/position
```

Response:
```json
{
  "value": {
    "latitude": 29.9511,
    "longitude": -90.0715
  },
  "timestamp": "2025-01-17T12:00:00.000Z"
}
```

### Timezone Detection

1. Position is fetched from Signal K
2. Latitude/longitude converted to timezone using `timezonefinder`
3. Timezone cached for 10 minutes
4. Falls back to UTC if unavailable

## Data Retention

By default, InfluxDB retains data according to your bucket's retention policy. For sail racing analysis, consider:

- **Short-term**: Keep detailed data for current season
- **Long-term**: Downsample or export historical data

### Example Downsampling Task

```flux
option task = {name: "downsample_sail_config", every: 1d}

from(bucket: "default")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "sail_config")
  |> aggregateWindow(every: 1h, fn: last)
  |> to(bucket: "sail_config_archive")
```
