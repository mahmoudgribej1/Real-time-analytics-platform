import { createContext, useContext, useState } from "react";

const CityContext = createContext({ city: "Tunis", setCity: () => {} });

export function CityProvider({ children }) {
    const [city, setCity] = useState("Tunis");
    return <CityContext.Provider value={{ city, setCity }}>{children}</CityContext.Provider>;
}

export const useCity = () => useContext(CityContext);
