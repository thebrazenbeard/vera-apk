package com.vera.companion;

import org.junit.Test;
import static org.junit.Assert.*;

public final class EndpointPolicyTest {
    @Test public void acceptsHttpsTailnet() {
        assertEquals("https://lappy.tail86ea75.ts.net:8443",
                EndpointPolicy.normalize(" https://LAPPY.tail86ea75.ts.net:8443/ "));
    }
    @Test public void refusesHttp() { reject("http://lappy.tail86ea75.ts.net:8443"); }
    @Test public void refusesIp() { reject("https://100.88.50.35:8443"); }
    @Test public void refusesPublicHost() { reject("https://example.com"); }
    @Test public void refusesCredentials() { reject("https://user:pw@lappy.tail.ts.net"); }
    @Test public void refusesPath() { reject("https://lappy.tail.ts.net/other"); }
    @Test public void refusesQuery() { reject("https://lappy.tail.ts.net/?k=1"); }
    @Test public void refusesPort() { reject("https://lappy.tail.ts.net:8080"); }
    private static void reject(String url) {
        try { EndpointPolicy.normalize(url); fail("accepted " + url); }
        catch (IllegalArgumentException expected) { /* fail closed */ }
    }
}
