# Coursera — certifications gratuites et formations en ligne
# On scrape les catégories "free" et "financial aid available"
import scrapy, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider

class CourseraFreeSpider(BaseOpportunitySpider):
    name = "coursera_free"
    custom_settings = { "DOWNLOAD_DELAY": 2, "ROBOTSTXT_OBEY": True }

    # Certifications Google, Meta, IBM — très demandées et gratuites avec aide financière
    CERTS = [
        {"title": "Google Data Analytics Certificate", "url": "https://www.coursera.org/professional-certificates/google-data-analytics", "field": "Informatique", "duration": "6 mois", "skills": ["SQL","R","Tableau","Excel","Data Analysis"]},
        {"title": "Google Project Management Certificate", "url": "https://www.coursera.org/professional-certificates/google-project-management", "field": "Gestion", "duration": "6 mois", "skills": ["Gestion de projet","Agile","Scrum","Communication"]},
        {"title": "Google IT Support Certificate", "url": "https://www.coursera.org/professional-certificates/google-it-support", "field": "Informatique", "duration": "6 mois", "skills": ["IT Support","Linux","Networking","Python"]},
        {"title": "IBM Data Science Professional Certificate", "url": "https://www.coursera.org/professional-certificates/ibm-data-science", "field": "Informatique", "duration": "11 mois", "skills": ["Python","Machine Learning","SQL","Data Science"]},
        {"title": "Meta Front-End Developer Certificate", "url": "https://www.coursera.org/professional-certificates/meta-front-end-developer", "field": "Informatique", "duration": "7 mois", "skills": ["React","JavaScript","HTML/CSS","UX Design"]},
        {"title": "Certificat Banque Mondiale : Développement Afrique", "url": "https://olc.worldbank.org/", "field": "Économie", "duration": "4-8 semaines", "skills": ["Développement économique","Politique publique","Finance"]},
        {"title": "CISCO Networking Academy (gratuit)", "url": "https://www.netacad.com/", "field": "Réseaux & Télécoms", "duration": "Variable", "skills": ["Cisco","Networking","Cybersécurité","Linux"]},
        {"title": "AWS Cloud Practitioner Essentials (gratuit)", "url": "https://aws.amazon.com/fr/training/digital/aws-cloud-practitioner-essentials/", "field": "Informatique", "duration": "6 heures", "skills": ["AWS","Cloud","Architecture"]},
        {"title": "Certification Microsoft Azure Fundamentals", "url": "https://learn.microsoft.com/fr-fr/certifications/azure-fundamentals/", "field": "Informatique", "duration": "3-5 jours", "skills": ["Azure","Cloud","Microsoft"]},
        {"title": "Google UX Design Certificate", "url": "https://www.coursera.org/professional-certificates/google-ux-design", "field": "Informatique", "duration": "7 mois", "skills": ["UX Design","Figma","Prototypage","Recherche utilisateur"]},
    ]

    def start_requests(self):
        # On génère directement les items sans scraper (les URLs sont connues et stables)
        for cert in self.CERTS:
            yield scrapy.Request(cert["url"], callback=self.parse_cert, meta={"cert": cert}, dont_filter=True)

    def parse_cert(self, response):
        cert = response.meta["cert"]
        description = (
            f"Certification professionnelle reconnue mondialement. "
            f"Compétences : {', '.join(cert['skills'])}. "
            f"Durée estimée : {cert['duration']}. "
            f"Aide financière disponible (bourses Coursera) — postuler directement sur la plateforme. "
            f"100% en ligne, à ton rythme. Certificat partageable sur LinkedIn."
        )
        yield self.make_opportunity_item(
            title=cert["title"], description=description, source_url=cert["url"],
            deadline=None, country="En ligne (International)", opp_type="formation",
            required_level=["Licence","Master","BTS","Ingénieur"],
            required_fields=[cert["field"]], required_languages=["en"], min_gpa=None,
        )
