"""Seed the knowledge base with static general-knowledge facts."""
from vector_store import VectorStore

SEED_FACTS = [
    {
        "text": "The Earth is approximately 4.54 billion years old, based on radiometric dating of meteorite material.",
        "source": "https://www.nasa.gov/solar-system/earth/",
        "details": "NASA - Earth Facts",
    },
    {
        "text": "The Earth is an oblate spheroid, not flat. This has been confirmed by satellite imagery, physics, and centuries of scientific observation.",
        "source": "https://www.nasa.gov/solar-system/earth/",
        "details": "NASA - Earth Shape",
    },
    {
        "text": "COVID-19 vaccines authorized by WHO have undergone rigorous clinical trials and have been shown to be safe and effective at preventing severe illness and death.",
        "source": "https://www.who.int/emergencies/diseases/novel-coronavirus-2019/covid-19-vaccines",
        "details": "WHO - COVID-19 Vaccine Safety",
    },
    {
        "text": "The Moon landing on July 20, 1969, by Apollo 11 astronauts Neil Armstrong and Buzz Aldrin is one of the most well-documented events in history, confirmed by independent sources worldwide.",
        "source": "https://www.nasa.gov/mission_pages/apollo/apollo11.html",
        "details": "NASA - Apollo 11 Mission",
    },
    {
        "text": "Climate change is primarily driven by human activities, especially the burning of fossil fuels, which increases greenhouse gas concentrations in the atmosphere. This is the scientific consensus supported by 97% of climate scientists.",
        "source": "https://climate.nasa.gov/scientific-consensus/",
        "details": "NASA - Scientific Consensus on Climate Change",
    },
    {
        "text": "5G technology uses radio waves and does not cause COVID-19 or other diseases. Radio waves in the 5G spectrum are non-ionizing and do not damage DNA or cells.",
        "source": "https://www.who.int/news-room/questions-and-answers/item/radiation-5g-mobile-networks-and-health",
        "details": "WHO - 5G and Health",
    },
    {
        "text": "Water fluoridation at recommended levels (0.7 mg/L) is safe and effective for preventing tooth decay, according to decades of research.",
        "source": "https://www.cdc.gov/fluoridation/",
        "details": "CDC - Community Water Fluoridation",
    },
    {
        "text": "The speed of light in a vacuum is approximately 299,792,458 meters per second. This is a fundamental constant of physics.",
        "source": "https://www.nist.gov/si-redefinition/meter",
        "details": "NIST - Speed of Light",
    },
    {
        "text": "India gained independence from British colonial rule on August 15, 1947. Jawaharlal Nehru became the first Prime Minister of independent India.",
        "source": "https://www.britannica.com/place/India/Independence",
        "details": "Britannica - Indian Independence",
    },
    {
        "text": "The United Nations was established on October 24, 1945, after World War II, with the aim of preventing future conflicts. It currently has 193 member states.",
        "source": "https://www.un.org/en/about-us",
        "details": "United Nations - About Us",
    },
]


def seed():
    """Load seed facts into the vector store if it's empty."""
    vs = VectorStore()
    if vs.count() > 0:
        print(f"KB already has {vs.count()} documents. Skipping seed.")
        return
    vs.add_documents_batch(SEED_FACTS)
    print(f"Seeded {len(SEED_FACTS)} facts into the knowledge base.")


if __name__ == "__main__":
    seed()
