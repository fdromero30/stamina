package com.stamina.usersconfig.trading.controller;

import com.stamina.usersconfig.trading.client.EtoroClient;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/etoro/market-data")
public class EtoroMarketDataController {

    private final EtoroClient etoroClient;

    public EtoroMarketDataController(EtoroClient etoroClient) {
        this.etoroClient = etoroClient;
    }

    @GetMapping("/search")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> search(
            @RequestParam("userId") UUID userId,
            @RequestParam("q") String query,
            @RequestParam(value = "fields", defaultValue = "instrumentId,internalSymbolFull,displayname") String fields) {
        try {
            return etoroClient.searchInstruments(userId, query, fields);
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro search failed: " + e.getMessage());
        }
    }

    @GetMapping("/rates")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> rates(
            @RequestParam("userId") UUID userId,
            @RequestParam("instrumentIds") List<Integer> instrumentIds) {
        try {
            return etoroClient.getInstrumentRates(userId, instrumentIds);
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro rates failed: " + e.getMessage());
        }
    }

    @GetMapping("/candles/{instrumentId}")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> candles(
            @RequestParam("userId") UUID userId,
            @PathVariable("instrumentId") int instrumentId,
            @RequestParam(value = "direction", defaultValue = "desc") String direction,
            @RequestParam(value = "interval", defaultValue = "1h") String interval,
            @RequestParam(value = "count", defaultValue = "100") int count) {
        try {
            return etoroClient.getCandles(userId, instrumentId, direction, interval, count);
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro candles failed: " + e.getMessage());
        }
    }
}